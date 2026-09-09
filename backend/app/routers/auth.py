"""Auth: register / login → bearer session → /me → logout."""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..display_name import teacher_display_name
from ..database import get_db
from ..deps import bearer_scheme, get_current_person
from ..models import AuthSession, Person
from ..payloads import validate_person_payload
from ..security import hash_password, new_token, verify_password
from ..seed import seed
from ..unassigned import ensure_unassigned_class
from ..workspace import ensure_workspace_id

router = APIRouter(prefix="/auth", tags=["auth"])

DEMO_TEACHER_EMAIL = "chen@school.edu"


class RegisterIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    email: str
    password: str = Field(min_length=6, max_length=64)
    phone: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


def normalize_phone(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email_format(email: str) -> None:
    if "@" not in email or len(email) < 3:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")


def validate_phone_format(phone: str) -> None:
    if not re.fullmatch(r"\d{6,15}", phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")


def user_out(u: Person) -> dict:
    payload = u.payload or {}
    role = payload.get("role")
    name = u.name
    out = {
        "id": str(u.id),
        "name": name,
        "phone": u.phone,
        "email": u.email,
        "role": role,
    }
    if role == "teacher":
        out["display_name"] = teacher_display_name(name)
    else:
        out["display_name"] = name or ""
    return out


def create_session(db: Session, person_id) -> str:
    token = new_token()
    db.add(AuthSession(token=token, person_id=person_id))
    return token


@router.get("/setup")
def setup_status(db: Session = Depends(get_db)):
    """Tell the login page whether first-time bootstrap is available."""
    role = Person.payload["role"].as_string()
    teachers = db.query(Person).filter(role == "teacher").count()
    demo = db.query(Person).filter(Person.email == DEMO_TEACHER_EMAIL).first()
    return {
        "needs_bootstrap": teachers == 0,
        "has_demo_account": demo is not None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = normalize_email(body.email)
    validate_email_format(email)
    if db.query(Person).filter(Person.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="该邮箱已注册")

    phone = None
    if body.phone:
        phone = normalize_phone(body.phone)
        validate_phone_format(phone)
        if db.query(Person).filter(Person.phone == phone).first() is not None:
            raise HTTPException(status_code=409, detail="该手机号已注册")

    ensure_unassigned_class(db)
    payload = validate_person_payload("teacher", {})
    person = Person(
        name=(body.name or "").strip() or email.split("@")[0],
        email=email,
        phone=phone,
        password_hash=hash_password(body.password),
        payload=payload,
    )
    db.add(person)
    db.flush()
    ensure_workspace_id(person)
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
    teacher = db.query(Person).filter(Person.email == DEMO_TEACHER_EMAIL).one()
    token = create_session(db, teacher.id)
    db.commit()
    return {"token": token, "user": user_out(teacher)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = normalize_email(body.email)
    person = db.query(Person).filter(Person.email == email).first()
    if person is None or not verify_password(body.password, person.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
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
