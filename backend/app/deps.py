"""Request-scoped auth dependencies."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, Person

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_person(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Person:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    session = db.get(AuthSession, credentials.credentials)
    if session is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    person = db.get(Person, session.person_id)
    if person is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return person


def require_admin(person: Person = Depends(get_current_person)) -> Person:
    if not person.is_admin:
        raise HTTPException(status_code=403, detail="admin only")
    return person


# Load-bearing alias: app/main.py passes get_current_user into
# include_router(dependencies=[...]) for every business router.
get_current_user = get_current_person
