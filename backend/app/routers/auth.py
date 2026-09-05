"""Auth: login → bearer session → /me → logout.

There is no self-registration. The app has exactly one teacher account (the
signed-in homeroom teacher) plus an admin; accounts come from the seed or the
admin's database tooling. An open register endpoint would mint a second
teacher with full access to the workplace's data.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import bearer_scheme, get_current_person
from ..models import AuthSession, Person
from ..security import new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    phone: str
    password: str


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "")


def user_out(u: Person) -> dict:
    payload = u.payload or {}
    return {
        "id": str(u.id),
        "name": u.name,
        "phone": u.phone,
        "email": u.email,
        "role": payload.get("role"),
    }


def create_session(db: Session, person_id) -> str:
    token = new_token()
    db.add(AuthSession(token=token, person_id=person_id))
    return token


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.phone == normalize_phone(body.phone)).first()
    if person is None or not verify_password(body.password, person.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    token = create_session(db, person.id)
    db.commit()
    return {"token": token, "user": user_out(person)}


@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        session = db.get(AuthSession, credentials.credentials)
        if session is not None:
            db.delete(session)
            db.commit()
    return {"ok": True}


@router.get("/me")
def me(person: Person = Depends(get_current_person)):
    return user_out(person)
