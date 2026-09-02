"""Developer-only admin routes. Guarded by get_admin_teacher — regular
teachers cannot hit these endpoints even if they guess the URL."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..deps import get_admin_teacher
from ..models import (
    AuthSession,
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    HomeVisit,
    Student,
    StudentEvent,
    Teacher,
)
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])

# All models that map to real DB tables — used for table-count introspection.
ALL_MODELS = [
    Teacher, Student, Class, Enrollment, Exam, ExamSubject, ExamResult,
    HomeVisit, StudentEvent, AuthSession,
]


@router.get("/stats")
def admin_stats(
    db: Session = Depends(get_db),
    _teacher: Teacher = Depends(get_admin_teacher),
):
    """Per-table row counts + database info."""
    counts = {m.__tablename__: db.query(m).count() for m in ALL_MODELS}
    return {
        "database": engine.url.drivername,
        "tables": counts,
        "teachers_total": counts.get("teacher", 0),
        "teachers_admins": db.query(Teacher).filter(Teacher.is_admin.is_(True)).count(),
        "teachers_active": db.query(Teacher).filter(Teacher.is_active.is_(True)).count(),
        "sessions_active": counts.get("auth_session", 0),
    }


@router.get("/teachers")
def list_teachers(
    db: Session = Depends(get_db),
    _teacher: Teacher = Depends(get_admin_teacher),
):
    teachers = db.query(Teacher).order_by(Teacher.id).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "phone": t.phone,
            "email": t.email,
            "subject": t.subject,
            "is_active": t.is_active,
            "is_admin": t.is_admin,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in teachers
    ]


class TeacherUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None
    password: str | None = None


@router.patch("/teachers/{teacher_id}")
def update_teacher(
    teacher_id: int,
    body: TeacherUpdate,
    db: Session = Depends(get_db),
    me: Teacher = Depends(get_admin_teacher),
):
    t = db.get(Teacher, teacher_id)
    if t is None:
        raise HTTPException(status_code=404, detail="教师不存在")
    # Don't allow an admin to demote themselves — would lock them out.
    if teacher_id == me.id and body.is_admin is False:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
    if body.is_active is not None:
        t.is_active = body.is_active
    if body.is_admin is not None:
        t.is_admin = body.is_admin
    if body.password:
        t.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.delete("/teachers/{teacher_id}")
def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    me: Teacher = Depends(get_admin_teacher),
):
    if teacher_id == me.id:
        raise HTTPException(status_code=400, detail="不能删除自己")
    t = db.get(Teacher, teacher_id)
    if t is None:
        raise HTTPException(status_code=404, detail="教师不存在")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    _teacher: Teacher = Depends(get_admin_teacher),
):
    sessions = (
        db.query(AuthSession, Teacher)
        .join(Teacher, Teacher.id == AuthSession.teacher_id)
        .order_by(AuthSession.created_at.desc())
        .all()
    )
    return [
        {
            "token": sess.token[:8] + "…",
            "teacher_id": teacher.id,
            "teacher_name": teacher.name,
            "created_at": sess.created_at.isoformat() if sess.created_at else None,
        }
        for sess, teacher in sessions
    ]


@router.delete("/sessions/{token_prefix}")
def kill_session(
    token_prefix: str,
    db: Session = Depends(get_db),
    _teacher: Teacher = Depends(get_admin_teacher),
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
    _teacher: Teacher = Depends(get_admin_teacher),
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
    _teacher: Teacher = Depends(get_admin_teacher),
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
    _teacher: Teacher = Depends(get_admin_teacher),
):
    """Drop all tables and recreate them — wipes everything. Intentionally
    does NOT call seed(), so the DB will be empty after this."""
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重置失败: {e}")
    return {"ok": True, "note": "数据库已清空并重建，请通过后端 seed 脚本重新初始化演示数据。"}
