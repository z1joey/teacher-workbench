"""Developer-only admin routes. Guarded by require_admin — teacher-role
persons cannot hit these endpoints even if they guess the URL."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..app_settings import is_registration_enabled, set_registration_enabled
from .. import database
from ..bootstrap_db import wipe_and_rebootstrap
from ..database import get_db
from ..deps import bearer_scheme, require_admin
from ..models import AuthSession, Class, Enrollment, Event, Feedback, Person, Tag
from ..payloads import validate_person_payload
from ..security import hash_password
from ..workspace import build_workspace_admin_maps, workspace_id, workspace_owner_label

router = APIRouter(prefix="/admin", tags=["admin"])

LIST_USER_ROLES = ("admin", "teacher", "student", "guardian")

# All models that map to real DB tables — used for table-count introspection.
ALL_MODELS = [Person, AuthSession, Event, Tag, Class, Enrollment, Feedback]


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Per-table row counts + database info."""
    counts = {m.__tablename__: db.query(m).count() for m in ALL_MODELS}
    # JSON booleans don't survive a SQL comparison portably: SQLite's
    # json_extract maps them to 1/0 (as_string() → '1', never 'false') while
    # PostgreSQL's ->> yields text. Count in Python with the same
    # default-true rule the users list uses.
    persons = db.query(Person).all()
    login_roles = {"teacher", "admin"}

    def _role(p: Person) -> str | None:
        return (p.payload or {}).get("role")

    persons_total = counts.get("person", 0)
    accounts_total = sum(1 for p in persons if _role(p) in login_roles)
    return {
        "database": database.engine.url.drivername,
        "tables": counts,
        # users_total kept for older clients — same as persons_total
        "users_total": persons_total,
        "persons_total": persons_total,
        "accounts_total": accounts_total,
        "users_admins": (
            db.query(Person).filter(Person.payload["role"].as_string() == "admin").count()
        ),
        "users_active": persons_total,
        "accounts_active": accounts_total,
        "sessions_active": counts.get("auth_session", 0),
    }


def _user_workspace_fields(
    u: Person,
    *,
    teachers_by_wid: dict[str, Person],
    label_for_wid,
    guardian_labels: dict,
) -> dict:
    role = u.role
    payload = u.payload or {}
    wid = payload.get("workspace_id")
    owner_id = None
    label = None

    if role == "teacher":
        wid = wid or workspace_id(u)
        owner_id = u.id
        label = workspace_owner_label(u)
    elif role == "student":
        owner = teachers_by_wid.get(wid or "")
        owner_id = owner.id if owner else None
        label = label_for_wid(wid)
    elif role == "guardian":
        labels = guardian_labels.get(u.id, [])
        label = "、".join(labels) if labels else None
    elif role == "admin":
        label = "系统"

    return {
        "workspace_id": wid,
        "workspace_owner_id": str(owner_id) if owner_id else None,
        "workspace_label": label,
    }


@router.get("/users")
def list_users(
    role: str | None = None,
    workspace_owner_id: str | None = None,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    query = db.query(Person).order_by(Person.id)
    if role is not None:
        if role not in LIST_USER_ROLES:
            raise HTTPException(status_code=400, detail="角色不合法")
        query = query.filter(Person.payload["role"].as_string() == role)
    teachers_by_wid, label_for_wid, guardian_labels = build_workspace_admin_maps(db)
    owner_uuid = None
    if workspace_owner_id:
        try:
            owner_uuid = uuid.UUID(workspace_owner_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="工作区参数不合法")
        owner = db.get(Person, owner_uuid)
        if owner is None or owner.role != "teacher":
            raise HTTPException(status_code=400, detail="工作区参数不合法")
        owner_wid = workspace_id(owner)

    rows = []
    for u in query.all():
        ws = _user_workspace_fields(
            u,
            teachers_by_wid=teachers_by_wid,
            label_for_wid=label_for_wid,
            guardian_labels=guardian_labels,
        )
        if owner_uuid is not None:
            if u.role == "teacher" and u.id != owner_uuid:
                continue
            if u.role == "student" and ws["workspace_id"] != owner_wid:
                continue
            if u.role == "guardian":
                owner_label = label_for_wid(owner_wid)
                if not owner_label or owner_label not in (ws["workspace_label"] or ""):
                    continue
            if u.role == "admin":
                continue
        rows.append(
            {
                "id": str(u.id),
                "name": u.name,
                "phone": u.phone,
                "email": u.email,
                "role": u.role,
                "admission_no": (u.payload or {}).get("admission_no")
                if u.role == "student"
                else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                **ws,
            }
        )
    return rows


class UserUpdate(BaseModel):
    role: str | None = None
    password: str | None = None


class SiteSettingsOut(BaseModel):
    registration_enabled: bool


class SiteSettingsUpdate(BaseModel):
    registration_enabled: bool


@router.get("/settings")
def get_site_settings(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    return SiteSettingsOut(registration_enabled=is_registration_enabled(db))


@router.patch("/settings")
def update_site_settings(
    body: SiteSettingsUpdate,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    set_registration_enabled(db, body.registration_enabled)
    db.commit()
    return SiteSettingsOut(registration_enabled=body.registration_enabled)


@router.patch("/users/{user_id}")
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    me: Person = Depends(require_admin),
):
    u = db.get(Person, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    # A role change rebuilds the payload from scratch, which would wipe a
    # student's admission_no/birth_date/guardian fields. Student profiles
    # are managed on /students instead.
    if (u.payload or {}).get("role") == "student":
        raise HTTPException(status_code=400, detail="学生账号不支持此操作")
    # Don't allow an admin to demote themselves — no in-app recovery.
    if user_id == me.id and body.role is not None and body.role != "admin":
        raise HTTPException(status_code=400, detail="不能降级自己的角色")
    payload = dict(u.payload or {})
    if body.role is not None:
        if body.role not in ("admin", "teacher"):
            raise HTTPException(status_code=400, detail="角色不合法")
        payload = validate_person_payload(body.role, {})
    u.payload = payload  # reassign: JSON columns don't see in-place mutation
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    me: Person = Depends(require_admin),
):
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    u = db.get(Person, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if (u.payload or {}).get("role") == "student":
        raise HTTPException(status_code=400, detail="学生账号不支持此操作")
    referenced = db.query(Enrollment.id).filter(Enrollment.person_id == user_id).first()
    if referenced is not None:
        raise HTTPException(status_code=409, detail="该账号仍有关联记录，无法删除")
    # Login sessions go with the account (tags/events ride the ORM's
    # many-to-many secondary cleanup; the payload is dropped with the row).
    db.query(AuthSession).filter(AuthSession.person_id == user_id).delete()
    db.delete(u)
    db.commit()
    return {"ok": True}


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    sessions = (
        db.query(AuthSession, Person)
        .join(Person, Person.id == AuthSession.person_id)
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    return [
        {
            "token": sess.token[:8] + "…",
            "user_id": str(person.id),
            "user_name": person.name,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
        }
        for sess, person in sessions
    ]


@router.delete("/sessions/{token_prefix}")
def kill_session(
    token_prefix: str,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Revoke a session by its 8-char prefix (as shown in /sessions)."""
    sessions = db.query(AuthSession).filter(AuthSession.token.startswith(token_prefix)).all()
    if not sessions:
        raise HTTPException(status_code=404, detail="会话不存在")
    for s in sessions:
        db.delete(s)
    db.commit()
    return {"ok": True, "deleted": len(sessions)}


@router.post("/sessions/kill-all")
def kill_all_sessions(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    db.query(AuthSession).delete()
    db.commit()
    return {"ok": True}


INSPECT_PAGE_SIZE = 20


class InspectIn(BaseModel):
    table: str
    page: int = 1


TABLE_ALLOWLIST = {m.__tablename__ for m in ALL_MODELS}


@router.get("/inspect/tables")
def inspect_tables(_me: Person = Depends(require_admin)):
    """Inspectable ORM tables (current schema only)."""
    return {"tables": sorted(TABLE_ALLOWLIST)}


@router.post("/inspect")
def inspect_table(
    body: InspectIn,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Preview rows from any known table — read-only."""
    if body.table not in TABLE_ALLOWLIST:
        raise HTTPException(status_code=400, detail="未知数据表")
    if body.page < 1:
        raise HTTPException(status_code=400, detail="page 需 >= 1")

    # Safer: resolve model from table name and query via ORM.
    model = next(m for m in ALL_MODELS if m.__tablename__ == body.table)
    pk_col = None
    for col in model.__table__.columns:
        if col.primary_key:
            pk_col = col
            break
    base_query = db.query(model)
    total = base_query.count()
    query = base_query
    if pk_col is not None:
        query = query.order_by(pk_col.desc())
    rows = (
        query.offset((body.page - 1) * INSPECT_PAGE_SIZE)
        .limit(INSPECT_PAGE_SIZE)
        .all()
    )
    total_pages = (total + INSPECT_PAGE_SIZE - 1) // INSPECT_PAGE_SIZE if total else 0

    # Use model's column attrs so we don't hit lazy-loaded relationships.
    columns = [c.key for c in model.__table__.columns]

    def _clean(v):
        if isinstance(v, datetime):
            return v.isoformat()
        if hasattr(v, "isoformat"):
            try:
                return v.isoformat()
            except Exception:
                return str(v)
        return v

    row_dicts = []
    for r in rows:
        row_dicts.append([_clean(getattr(r, c)) for c in columns])

    return {
        "table": body.table,
        "columns": columns,
        "rows": row_dicts,
        "page": body.page,
        "page_size": INSPECT_PAGE_SIZE,
        "total": total,
        "total_pages": total_pages,
    }


@router.post("/db/reset")
def reset_db(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Drop all tables and rebuild via alembic bootstrap (not raw create_all).

    Auth is checked on a short-lived session that closes before DDL so
    PostgreSQL does not deadlock. All sessions are wiped; caller must
    re-login (or use ADMIN_EMAIL bootstrap after restart).
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    with Session(database.engine, autoflush=False, expire_on_commit=False) as db:
        session = db.get(AuthSession, credentials.credentials)
        if session is None:
            raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
        person = db.get(Person, session.person_id)
        if person is None or not person.is_admin:
            raise HTTPException(status_code=403, detail="admin only")
    try:
        wipe_and_rebootstrap()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")
    return {
        "ok": True,
        "relogin_required": True,
        "note": "数据库已清空并重建。请重新登录；演示数据可通过 seed 脚本或教师端「加载演示数据」导入。",
    }


@router.get("/feedback")
def admin_feedback(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """用户反馈列表（最新在前，含作者信息）。"""
    from .feedback import list_feedback

    return list_feedback(db)


@router.get("/feedback/unresolved-count")
def admin_feedback_unresolved_count(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    from .feedback import unresolved_feedback_count

    return {"count": unresolved_feedback_count(db)}


class FeedbackResolveIn(BaseModel):
    resolved: bool


@router.patch("/feedback/{feedback_id}")
def admin_feedback_resolve(
    feedback_id: uuid.UUID,
    body: FeedbackResolveIn,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    from .feedback import feedback_out, set_feedback_resolved

    fb = set_feedback_resolved(db, feedback_id, body.resolved)
    author = db.get(Person, fb.person_id)
    db.commit()
    return feedback_out(fb, author=author)


@router.delete("/feedback/{feedback_id}")
def admin_feedback_delete(
    feedback_id: uuid.UUID,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    from .feedback import delete_feedback

    delete_feedback(db, feedback_id)
    db.commit()
    return {"ok": True}
