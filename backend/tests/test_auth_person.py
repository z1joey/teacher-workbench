"""Behavior lock for the auth core: login → /me → logout over
app.routers.auth, plus the /profile and /teachers reads that ride on the same
identity. There is no self-registration: the app has exactly one teacher
account (the signed-in homeroom teacher), so /auth/register must stay dead."""
from __future__ import annotations

from app.models import Person
from app.routers import auth, misc, profile
from tests.conftest import seed_person, seed_token


def _auth_client(make_client):
    # /login must be open; /me and /logout guard themselves.
    return make_client(auth.router, auth_dependency=False)


def test_register_route_is_gone(make_client):
    """Single-teacher app: self-registration must never come back — a fresh
    register endpoint would mint a second teacher with full data access."""
    client = _auth_client(make_client)
    r = client.post("/api/auth/register",
                    json={"phone": "13800000000", "password": "secret123"})
    assert r.status_code == 404


def test_login_me_logout_flow(make_client, db):
    client = _auth_client(make_client)
    person = seed_person(db, "13800000000", name="李老师")
    db.commit()

    r = client.post("/api/auth/login", json={"phone": "13800000000", "password": "123456"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["name"] == "李老师"
    headers = {"Authorization": f"Bearer {body['token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert set(me.json()) == {"id", "name", "phone", "email", "role"}
    assert me.json()["id"] == body["user"]["id"]
    assert me.json()["role"] == "teacher"

    assert client.post("/api/auth/logout", headers=headers).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_login_wrong_password_401(make_client, db):
    client = _auth_client(make_client)
    seed_person(db, "13800000012", name="王老师")
    r = client.post("/api/auth/login", json={"phone": "13800000012", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_without_token_401(make_client):
    client = _auth_client(make_client)
    assert client.get("/api/auth/me").status_code == 401


def test_disabled_person_gets_403_on_me(make_client, db):
    client = _auth_client(make_client)
    person = seed_person(db, "13800000014", active=False)
    token = seed_token(db, person, "a" * 64)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_profile_patch_get_round_trips_name(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "13800000015", name="陈老师")
    token = seed_token(db, person, "b" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/profile", json={"name": "陈老师"}, headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"id", "name", "phone", "email", "role"}
    assert r.json()["name"] == "陈老师"

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"user", "classes", "stats", "semesters"}
    assert r.json()["user"]["name"] == "陈老师"
    semesters = r.json()["semesters"]
    assert len(semesters) == 6
    t1 = next(row for row in semesters if row["id"] == "2025-t1")
    t2 = next(row for row in semesters if row["id"] == "2025-t2")
    assert t1 == {
        "id": "2025-t1",
        "name": "2025-2026 第一学期",
        "start_date": "2025-09-01",
        "end_date": "2026-01-31",
    }
    assert t2["start_date"] == "2026-02-01"
    assert t2["end_date"] == "2026-07-31"
    db.refresh(person)
    assert not (person.payload or {}).get("semesters")


def test_profile_get_does_not_persist_default_semesters(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "13800000020", name="陈老师")
    token = seed_token(db, person, "e" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["semesters"]) == 6
    db.refresh(person)
    assert not (person.payload or {}).get("semesters")


def test_profile_semesters_patch_round_trip(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "13800000019", name="陈老师")
    token = seed_token(db, person, "d" * 64)
    headers = {"Authorization": f"Bearer {token}"}
    rows = [
        {
            "id": "2025-t1",
            "name": "2025-2026 第一学期",
            "start_date": "2025-09-01",
            "end_date": "2026-01-31",
        },
        {
            "id": "2025-t2",
            "name": "2025-2026 第二学期",
            "start_date": "2026-02-01",
            "end_date": "2026-07-31",
        },
    ]

    r = client.patch("/api/profile/semesters", json={"semesters": rows}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["semesters"] == rows

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["semesters"] == rows


def test_teachers_lists_only_teachers(make_client, db):
    client = make_client(misc.router)
    seed_person(db, "13800000016", name="张老师")
    seed_person(db, "13800000017", role="admin", name="管理员")
    seed_person(db, "13800000018", role="student", name="林小明", admission_no="S9")
    token = seed_token(db, db.query(Person).filter_by(phone="13800000016").one(), "c" * 64)

    r = client.get("/api/teachers", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["name"] for row in rows] == ["张老师"]
    assert set(rows[0]) == {"id", "name", "email"}
