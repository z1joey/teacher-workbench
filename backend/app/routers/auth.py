import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import bearer_scheme, get_current_teacher
from ..models import AuthSession, Teacher
from ..security import hash_password, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str
    password: str = Field(min_length=6, max_length=64)
    email: str | None = None


class LoginIn(BaseModel):
    phone: str
    password: str


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "")


def teacher_out(t: Teacher) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "phone": t.phone,
        "email": t.email,
        "subject": t.subject,
    }


def create_session(db: Session, teacher_id: int) -> str:
    token = new_token()
    db.add(AuthSession(token=token, teacher_id=teacher_id))
    return token


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    if not re.fullmatch(r"\d{6,15}", phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if body.email and "@" not in body.email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if db.query(Teacher).filter(Teacher.phone == phone).first() is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册")
    teacher = Teacher(
        name=body.name.strip(),
        phone=phone,
        email=(body.email or "").strip() or None,
        password_hash=hash_password(body.password),
    )
    db.add(teacher)
    db.flush()
    token = create_session(db, teacher.id)
    db.commit()
    return {"token": token, "teacher": teacher_out(teacher)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    teacher = db.query(Teacher).filter(Teacher.phone == normalize_phone(body.phone)).first()
    if teacher is None or not verify_password(body.password, teacher.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    token = create_session(db, teacher.id)
    db.commit()
    return {"token": token, "teacher": teacher_out(teacher)}


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
def me(teacher: Teacher = Depends(get_current_teacher)):
    return teacher_out(teacher)
