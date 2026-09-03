"""Direct-call unit tests for the User-based auth core (no TestClient —
routers are mid-migration when this lands)."""
import os

_TEST_DB_URI = "sqlite:///file:auth_user_tests?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = _TEST_DB_URI

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base  # noqa: E402
from app.deps import get_current_user, require_role  # noqa: E402
from app.models import AuthSession, TeacherProfile, User  # noqa: E402
from app.routers.auth import LoginIn, RegisterIn, login, register  # noqa: E402
from app.security import hash_password, new_token  # noqa: E402

engine = create_engine(
    _TEST_DB_URI, future=True, poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db():
    s = Session()
    yield s
    s.rollback()
    s.close()


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_register_creates_teacher_role_and_session(db):
    out = register(body=RegisterIn(name="新老师", phone="13900000001", password="123456"), db=db)
    assert out["user"]["role"] == "teacher"
    assert out["user"]["subject"] is None
    assert db.get(AuthSession, out["token"]).user_id == out["user"]["id"]


def test_register_cannot_mint_admin(db):
    # RegisterIn has no role field — the schema itself prevents privilege lifts.
    out = register(body=RegisterIn(name="提权尝试", phone="13900000002", password="123456"), db=db)
    assert out["user"]["role"] == "teacher"


def test_login_returns_role(db):
    _seed_user(db, "13900000011", "teacher")
    out = login(body=LoginIn(phone="13900000011", password="123456"), db=db)
    assert out["user"]["role"] == "teacher"


def test_login_wrong_password_401(db):
    _seed_user(db, "13900000012", "teacher")
    with pytest.raises(HTTPException) as ei:
        login(body=LoginIn(phone="13900000012", password="wrong-pass"), db=db)
    assert ei.value.status_code == 401


def _seed_user(db, phone: str, role: str, active: bool = True) -> User:
    u = User(name="用户", phone=phone, password_hash=hash_password("123456"),
             role=role, is_active=active)
    db.add(u)
    db.flush()
    return u


def test_get_current_user_resolves_session(db):
    u = _seed_user(db, "13900000003", "teacher")
    tok = new_token()
    db.add(AuthSession(token=tok, user_id=u.id))
    db.commit()
    assert get_current_user(credentials=_creds(tok), db=db).id == u.id


def test_get_current_user_inactive_401(db):
    u = _seed_user(db, "13900000004", "teacher", active=False)
    tok = new_token()
    db.add(AuthSession(token=tok, user_id=u.id))
    db.commit()
    with pytest.raises(HTTPException) as ei:
        get_current_user(credentials=_creds(tok), db=db)
    assert ei.value.status_code == 401


def test_require_role_gates(db):
    teacher = _seed_user(db, "13900000005", "teacher")
    with pytest.raises(HTTPException) as ei:
        require_role("admin")(user=teacher)
    assert ei.value.status_code == 403
    admin = _seed_user(db, "13900000006", "admin")
    assert require_role("admin")(user=admin).id == admin.id


def test_user_out_reads_subject_from_profile(db):
    u = _seed_user(db, "13900000007", "teacher")
    db.add(TeacherProfile(user_id=u.id, subject="math"))
    db.commit()
    from app.routers.auth import user_out
    assert user_out(u)["subject"] == "math"
    assert user_out(u)["role"] == "teacher"
