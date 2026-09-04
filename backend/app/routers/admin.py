"""Developer-only admin routes. Guarded by require_admin — teacher-role
persons cannot hit these endpoints even if they guess the URL."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..deps import require_admin
from ..models import AuthSession, Class, Enrollment, Event, Person, Tag
from ..payloads import validate_person_payload
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

# All models that map to real DB tables — used for table-count introspection.
ALL_MODELS = [Person, AuthSession, Event, Tag, Class, Enrollment]


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Per-table row counts + database info."""
    counts = {m.__tablename__: db.query(m).count() for m in ALL_MODELS}
    return {
        "database": engine.url.drivername,
        "tables": counts,
        "users_total": counts.get("person", 0),
        "users_admins": (
            db.query(Person).filter(Person.payload["role"].as_string() == "admin").count()
        ),
        "users_active": (
            db.query(Person)
            .filter(Person.payload["is_active"].as_string() != "false")
            .count()
        ),
        "sessions_active": counts.get("auth_session", 0),
    }


@router.get("/users")
def list_users(
    role: str | None = None,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    query = db.query(Person).order_by(Person.id)
    if role is not None:
        if role not in ("admin", "teacher"):
            raise HTTPException(status_code=400, detail="角色不合法")
        query = query.filter(Person.payload["role"].as_string() == role)
    return [
        {
            "id": str(u.id),
            "name": (u.payload or {}).get("name"),
            "phone": u.phone,
            "email": u.email,
            "subject": (u.payload or {}).get("subject"),
            "role": u.role,
            "is_active": (u.payload or {}).get("is_active") is not False,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in query.all()
    ]


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


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
    # Don't allow an admin to lock themselves out — demoting their role or
    # deactivating their account both make every subsequent request 401/403
    # with no in-app recovery.
    if user_id == me.id:
        if body.role is not None and body.role != "admin":
            raise HTTPException(status_code=400, detail="不能降级自己的角色")
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
    payload = dict(u.payload or {})
    if body.role is not None:
        if body.role not in ("admin", "teacher"):
            raise HTTPException(status_code=400, detail="角色不合法")
        # Re-validate under the new role: payload shapes differ (a teacher's
        # `subject` has no place in an admin payload and vice versa).
        payload = validate_person_payload(
            body.role,
            {
                "name": payload.get("name") or u.phone or "",
                "is_active": payload.get("is_active", True),
            },
        )
    if body.is_active is not None:
        payload["is_active"] = body.is_active
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
    # Evidence FKs (class.homeroom_person_id, enrollment.person_id) have no
    # cascades — only hard-delete unreferenced accounts; referenced ones hit
    # the 409 guard below.
    referenced = (
        db.query(Class.id).filter(Class.homeroom_person_id == user_id).first()
        or db.query(Enrollment.id).filter(Enrollment.person_id == user_id).first()
    )
    if referenced is not None:
        raise HTTPException(status_code=409, detail="该账号仍有关联记录，无法删除")
    # Login sessions go with the account (tags/events ride the ORM's
    # many-to-many secondary cleanup; subject lives in the payload now, so
    # the old teacher_profile bulk-delete is gone).
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
            "user_name": (person.payload or {}).get("name"),
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


class InspectIn(BaseModel):
    table: str
    limit: int = 20


TABLE_ALLOWLIST = {m.__tablename__ for m in ALL_MODELS}


@router.post("/inspect")
def inspect_table(
    body: InspectIn,
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Preview rows from any known table — read-only."""
    if body.table not in TABLE_ALLOWLIST:
        raise HTTPException(status_code=400, detail="未知数据表")
    if body.limit < 1 or body.limit > 100:
        raise HTTPException(status_code=400, detail="limit 需在 1–100 之间")

    # Safer: resolve model from table name and query via ORM.
    model = next(m for m in ALL_MODELS if m.__tablename__ == body.table)
    pk_col = None
    for col in model.__table__.columns:
        if col.primary_key:
            pk_col = col
            break
    query = db.query(model)
    if pk_col is not None:
        query = query.order_by(pk_col.desc())
    rows = query.limit(body.limit).all()

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
    }


@router.post("/db/reset")
def reset_db(
    db: Session = Depends(get_db),
    _me: Person = Depends(require_admin),
):
    """Drop all tables and recreate them — wipes everything. Intentionally
    does NOT call seed(), so the DB will be empty after this."""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")
    return {"ok": True, "note": "数据库已清空并重建，请通过后端 seed 脚本重新初始化演示数据。"}
