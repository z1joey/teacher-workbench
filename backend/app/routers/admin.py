"""Developer-only admin routes. Guarded by get_admin_user — teacher-role
users cannot hit these endpoints even if they guess the URL."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..deps import get_admin_user
from ..models import (
    AuthSession,
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    Student,
    StudentEvent,
    TeacherProfile,
    User,
)
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

# All models that map to real DB tables — used for table-count introspection.
ALL_MODELS = [
    User, TeacherProfile, Student, Class, Enrollment, Exam, ExamSubject,
    ExamResult, StudentEvent, AuthSession,
]


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_admin_user),
):
    """Per-table row counts + database info."""
    counts = {m.__tablename__: db.query(m).count() for m in ALL_MODELS}
    return {
        "database": engine.url.drivername,
        "tables": counts,
        "users_total": counts.get("user", 0),
        "users_admins": db.query(User).filter(User.role == "admin").count(),
        "users_active": db.query(User).filter(User.is_active.is_(True)).count(),
        "sessions_active": counts.get("auth_session", 0),
    }


@router.get("/users")
def list_users(
    role: str | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_admin_user),
):
    query = (
        db.query(User, TeacherProfile.subject)
        .outerjoin(TeacherProfile, TeacherProfile.user_id == User.id)
        .order_by(User.id)
    )
    if role is not None:
        if role not in ("admin", "teacher"):
            raise HTTPException(status_code=400, detail="角色不合法")
        query = query.filter(User.role == role)
    return [
        {
            "id": u.id,
            "name": u.name,
            "phone": u.phone,
            "email": u.email,
            "subject": subject,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u, subject in query.all()
    ]


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    me: User = Depends(get_admin_user),
):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if body.role is not None:
        if body.role not in ("admin", "teacher"):
            raise HTTPException(status_code=400, detail="角色不合法")
        # Don't allow an admin to demote themselves — would lock them out.
        if user_id == me.id and body.role != "admin":
            raise HTTPException(status_code=400, detail="不能降级自己的角色")
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    me: User = Depends(get_admin_user),
):
    if user_id == me.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    # FKs have no cascades — only hard-delete unreferenced accounts.
    referenced = (
        db.query(Class.id).filter(Class.homeroom_teacher_id == user_id).first()
        or db.query(ExamResult.id).filter(ExamResult.entered_by == user_id).first()
        or db.query(StudentEvent.id).filter(StudentEvent.actor_teacher_id == user_id).first()
    )
    if referenced is not None:
        raise HTTPException(status_code=409, detail="该账号仍有关联记录，无法删除")
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()
    db.delete(u)
    db.commit()
    return {"ok": True}


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    _user: User = Depends(get_admin_user),
):
    sessions = (
        db.query(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    return [
        {
            "token": sess.token[:8] + "…",
            "user_id": user.id,
            "user_name": user.name,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
        }
        for sess, user in sessions
    ]


@router.delete("/sessions/{token_prefix}")
def kill_session(
    token_prefix: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_admin_user),
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
    _user: User = Depends(get_admin_user),
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
    _user: User = Depends(get_admin_user),
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
    _user: User = Depends(get_admin_user),
):
    """Drop all tables and recreate them — wipes everything. Intentionally
    does NOT call seed(), so the DB will be empty after this."""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")
    return {"ok": True, "note": "数据库已清空并重建，请通过后端 seed 脚本重新初始化演示数据。"}
