"""Request-scoped auth dependency."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, Teacher

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_teacher(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    session = db.get(AuthSession, credentials.credentials)
    if session is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    teacher = db.get(Teacher, session.teacher_id)
    if teacher is None or not teacher.is_active:
        raise HTTPException(status_code=401, detail="账号不可用")
    return teacher
