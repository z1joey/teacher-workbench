import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import bearer_scheme, get_current_user
from ..models import AuthSession, User
from ..security import hash_password, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str
    password: str = Field(min_length=6, max_length=64)
    email: str | None = None
    # NOTE: deliberately no `role` — self-registration always mints teachers.


class LoginIn(BaseModel):
    phone: str
    password: str


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "")


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "phone": u.phone,
        "email": u.email,
        "subject": u.profile.subject if u.profile else None,
        "role": u.role,
    }


def create_session(db: Session, user_id: int) -> str:
    token = new_token()
    db.add(AuthSession(token=token, user_id=user_id))
    return token


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    if not re.fullmatch(r"\d{6,15}", phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if body.email and "@" not in body.email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if db.query(User).filter(User.phone == phone).first() is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册")
    user = User(
        name=body.name.strip(),
        phone=phone,
        email=(body.email or "").strip() or None,
        password_hash=hash_password(body.password),
        role="teacher",
    )
    db.add(user)
    db.flush()
    token = create_session(db, user.id)
    db.commit()
    return {"token": token, "user": user_out(user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == normalize_phone(body.phone)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    token = create_session(db, user.id)
    db.commit()
    return {"token": token, "user": user_out(user)}


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
def me(user: User = Depends(get_current_user)):
    return user_out(user)
