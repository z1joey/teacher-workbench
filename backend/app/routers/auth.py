"""Auth: register / login → bearer session → /me → logout.

Forgot-password: POST /auth/password/forgot emails a 6-digit code (Aliyun
DirectMail), POST /auth/password/reset verifies it against Redis (hashed,
attempt-capped) and swaps the password — killing every session of that
account. Both endpoints answer the same for unknown emails so account
existence never leaks.
"""
import re

import redis as redis_lib
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from ..directmail import MailError, send_html_mail
from ..display_name import teacher_display_name
from ..app_settings import is_registration_enabled
from ..database import get_db
from ..deps import bearer_scheme, get_current_person
from ..models import AuthSession, Person
from ..password_reset import (
    CodeError,
    PasswordCodeStore,
    RateLimited,
    build_reset_email,
    get_code_store,
)
from ..payloads import validate_person_payload
from ..security import hash_password, new_token, verify_password
from ..unassigned import ensure_unassigned_class
from ..workspace import ensure_workspace_id

router = APIRouter(prefix="/auth", tags=["auth"])


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
        "display_name": teacher_display_name(name, email=u.email),
    }
    return out


def create_session(db: Session, person_id) -> str:
    token = new_token()
    db.add(AuthSession(token=token, person_id=person_id))
    return token


@router.get("/registration-status")
def registration_status(db: Session = Depends(get_db)):
    return {"enabled": is_registration_enabled(db)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if not is_registration_enabled(db):
        raise HTTPException(status_code=403, detail="当前已关闭注册")
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
        name=(body.name or "").strip(),
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


# ------------------------------------------------------------- 忘记密码

class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    email: str
    code: str = Field(min_length=4, max_length=8)
    new_password: str = Field(min_length=6, max_length=64)


def get_mailer():
    """Dependency indirection so tests can stub the DirectMail call.
    注意：不要加返回注解——Callable 注解会让 FastAPI 把邮件函数再解析成子依赖。"""
    return send_html_mail


@router.post("/password/forgot")
def forgot_password(
    body: ForgotIn,
    db: Session = Depends(get_db),
    store: PasswordCodeStore = Depends(get_code_store),
    send_mail=Depends(get_mailer),
):
    """发送重置验证码。限流对任意邮箱一致生效（1 分钟冷却 / 每小时 5 封）；
    账号不存在或已停用时同样返回 ok，不泄露账号存在性。"""
    email = normalize_email(body.email)
    validate_email_format(email)
    try:
        code, _ = store.request_code(email)
    except RateLimited as e:
        raise HTTPException(
            status_code=429,
            detail=f"发送太频繁，请 {e.retry_after} 秒后再试",
            headers={"Retry-After": str(e.retry_after)},
        )
    except RedisError:
        raise HTTPException(status_code=503, detail="验证码服务暂不可用，请稍后再试")
    person = db.query(Person).filter(Person.email == email).first()
    if person is not None and (person.payload or {}).get("is_active", True) is not False:
        try:
            send_mail(email, "重置密码验证码", build_reset_email(code))
        except MailError:
            raise HTTPException(status_code=502, detail="邮件发送失败，请稍后再试")
    return {"ok": True}


@router.post("/password/reset")
def reset_password(
    body: ResetIn,
    db: Session = Depends(get_db),
    store: PasswordCodeStore = Depends(get_code_store),
):
    """校验验证码并重置密码；成功后吊销该账号全部会话，强制重新登录。"""
    email = normalize_email(body.email)
    person = db.query(Person).filter(Person.email == email).first()
    if person is None:
        raise HTTPException(status_code=400, detail="验证码错误或已过期")
    try:
        store.verify_and_consume(email, body.code)
    except CodeError as e:
        detail = (
            "尝试次数过多，请重新获取验证码"
            if e.reason == "exhausted"
            else "验证码错误或已过期"
        )
        raise HTTPException(status_code=400, detail=detail)
    except RedisError:
        raise HTTPException(status_code=503, detail="验证码服务暂不可用，请稍后再试")
    person.password_hash = hash_password(body.new_password)
    db.query(AuthSession).filter(AuthSession.person_id == person.id).delete()
    db.commit()
    return {"ok": True}


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=64)


@router.post("/password/change")
def change_password(
    body: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    """Authenticated password change: verifies the current password, keeps the
    current session alive and revokes every other session of the account."""
    if not verify_password(body.current_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if verify_password(body.new_password, user.password_hash or ""):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    user.password_hash = hash_password(body.new_password)
    if credentials is not None:
        db.query(AuthSession).filter(
            AuthSession.person_id == user.id,
            AuthSession.token != credentials.credentials,
        ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}
