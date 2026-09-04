"""Behavior lock for the Person-based auth core: register → login → /me →
logout over app.routers.auth, plus the /teachers and /profile reads that ride
on the same identity. Ports the scenarios of the deleted test_auth_user.py to
HTTP against a make_client(auth.router) app — the identity swap makes ids
UUID strings and turns disabled accounts into 403 (was 401)."""
from __future__ import annotations

import uuid

from app.models import AuthSession, Person
from app.payloads import validate_person_payload
from app.routers import auth, misc, profile
from app.security import hash_password


def _register(client, phone: str, password: str = "secret123", **extra):
    return client.post("/api/auth/register", json={"phone": phone, "password": password, **extra})


def _auth_client(make_client):
    # /register and /login must be open; /me and /logout guard themselves.
    return make_client(auth.router, auth_dependency=False)


def _seed_person(db, phone: str, *, role: str = "teacher", active: bool = True,
                 name: str = "用户", subject: str | None = None,
                 admission_no: str | None = None) -> Person:
    data = {"name": name}
    if subject is not None:
        data["subject"] = subject
    if admission_no is not None:
        data["admission_no"] = admission_no
    payload = validate_person_payload(role, data)
    if not active:
        payload["is_active"] = False
    p = Person(phone=phone, password_hash=hash_password("123456"), payload=payload)
    db.add(p)
    db.flush()
    return p


def _seed_token(db, person: Person, token: str) -> str:
    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return token


def test_register_login_me_logout_flow(make_client, db):
    client = _auth_client(make_client)
    r = _register(client, "13800000000", name="李老师")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["subject"] is None
    uuid.UUID(body["user"]["id"])  # id is a UUID string now
    assert db.get(AuthSession, body["token"]).person_id == uuid.UUID(body["user"]["id"])

    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "secret123"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert set(me.json()) == {"id", "name", "phone", "email", "subject", "role"}
    assert me.json()["id"] == body["user"]["id"]
    assert me.json()["name"] == "李老师"
    assert me.json()["role"] == "teacher"

    assert client.post("/api/auth/logout", headers=headers).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_register_cannot_mint_admin(make_client):
    # RegisterIn has no role field — the schema itself prevents privilege lifts.
    client = _auth_client(make_client)
    r = _register(client, "13800000002", password="123456", role="admin")
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "teacher"


def test_register_without_name_defaults_to_phone(make_client):
    # Minimal signup: no name (or blank) — the phone becomes the display name.
    client = _auth_client(make_client)
    r = _register(client, "13800000021", password="123456")
    assert r.json()["user"]["name"] == "13800000021"
    r = _register(client, "13800000022", password="123456", name="  ")
    assert r.json()["user"]["name"] == "13800000022"


def test_register_duplicate_phone_409(make_client):
    client = _auth_client(make_client)
    assert _register(client, "13800000013", password="123456").status_code == 201
    r = _register(client, "13800000013", password="123456", name="别人")
    assert r.status_code == 409


def test_login_wrong_password_401(make_client):
    client = _auth_client(make_client)
    assert _register(client, "13800000012", password="123456").status_code == 201
    r = client.post("/api/auth/login", json={"phone": "13800000012", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_without_token_401(make_client):
    client = _auth_client(make_client)
    assert client.get("/api/auth/me").status_code == 401


def test_disabled_person_gets_403_on_me(make_client, db):
    client = _auth_client(make_client)
    person = _seed_person(db, "13800000014", active=False)
    token = _seed_token(db, person, "a" * 64)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_profile_patch_get_round_trips_subject(make_client, db):
    client = make_client(profile.router)
    person = _seed_person(db, "13800000015", name="陈老师")
    token = _seed_token(db, person, "b" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/profile", json={"name": "陈老师", "subject": "math"}, headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"id", "name", "phone", "email", "subject", "role"}
    assert r.json()["subject"] == "math"

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"user", "classes", "stats"}
    assert r.json()["user"]["subject"] == "math"


def test_teachers_lists_only_teachers(make_client, db):
    client = make_client(misc.router)
    _seed_person(db, "13800000016", name="张老师", subject="语文")
    _seed_person(db, "13800000017", role="admin", name="管理员")
    _seed_person(db, "13800000018", role="student", name="林小明", admission_no="S9")
    token = _seed_token(db, db.query(Person).filter_by(phone="13800000016").one(), "c" * 64)

    r = client.get("/api/teachers", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["name"] for row in rows] == ["张老师"]
    assert rows[0]["subject"] == "语文"
    assert set(rows[0]) == {"id", "name", "subject", "email"}
