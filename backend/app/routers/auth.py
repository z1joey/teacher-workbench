"""Auth: register / login → bearer session → /me → logout."""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import bearer_scheme, get_current_person
from ..models import AuthSession, Person
from ..payloads import validate_person_payload
from ..security import hash_password, new_token, verify_password
from ..seed import seed
from ..unassigned import ensure_unassigned_class

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    phone: str
    password: str = Field(min_length=6, max_length=64)
    email: str | None = None


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


@router.get("/setup")
def setup_status(db: Session = Depends(get_db)):
    """Tell the login page whether first-time bootstrap is available."""
    role = Person.payload["role"].as_string()
    teachers = db.query(Person).filter(role == "teacher").count()
    demo = db.query(Person).filter(Person.phone == "13800000001").first()
    return {
        "needs_bootstrap": teachers == 0,
        "has_demo_account": demo is not None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    if not re.fullmatch(r"\d{6,15}", phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if body.email and "@" not in body.email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    if db.query(Person).filter(Person.phone == phone).first() is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册")
    ensure_unassigned_class(db)
    payload = validate_person_payload("teacher", {})
    person = Person(
        name=(body.name or "").strip() or phone,
        phone=phone,
        email=(body.email or "").strip() or None,
        password_hash=hash_password(body.password),
        payload=payload,
    )
    db.add(person)
    db.flush()
    token = create_session(db, person.id)
    db.commit()
    return {"token": token, "user": user_out(person)}


@router.post("/bootstrap")
def bootstrap_demo(db: Session = Depends(get_db)):
    """First-run only: load CLI demo data and sign in as the demo teacher."""
    role = Person.payload["role"].as_string()
    if db.query(Person).filter(role == "teacher").count() > 0:
        raise HTTPException(status_code=400, detail="已有教师账号，无法重复初始化")
    try:
        ensure_unassigned_class(db)
        seed(db)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"初始化失败: {exc}") from exc
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    token = create_session(db, teacher.id)
    db.commit()
    return {"token": token, "user": user_out(teacher)}


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
