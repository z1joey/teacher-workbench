"""Behavior lock for /admin/users: require_admin gating, role filtering,
update rules, delete-with-evidence guard. Adapted from the User-based file to
Person + payload identities: ids are UUID strings, is_active/name/subject live
in the payload, and tokens are seeded directly (make_client replaces the
full-app fixture while routers are mid-migration)."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models import AuthSession, Class, Enrollment, Person
from app.payloads import validate_person_payload
from app.routers import admin, auth
from app.security import hash_password

ADMIN_TOKEN = "a" * 64
TEACHER_TOKEN = "d" * 64
TEACHER2_TOKEN = "c" * 64


def _seed_person(db, phone: str, *, role: str = "teacher", active: bool = True,
                 name: str = "用户", subject: str | None = None) -> Person:
    data = {"name": name}
    if subject is not None:
        data["subject"] = subject
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


@pytest.fixture()
def client(make_client, db):
    """Fresh app + seeded data per test. Yields (TestClient, ids) with the
    admin token pre-set as Authorization header; tests needing another
    identity swap the header themselves. Admin endpoints carry their own
    require_admin guard, so the app mounts without a global auth dependency
    (exactly like app/main.py does)."""
    tc = make_client(auth.router, admin.router, auth_dependency=False)

    admin_p = _seed_person(db, "13600000000", role="admin", name="管理员")
    teacher = _seed_person(db, "13600000001", name="陈老师", subject="math")
    teacher2 = _seed_person(db, "13600000002", name="赵老师", subject="english")

    klass = Class(name="七年级1班", grade_level=7, academic_year="2025/2026",
                  homeroom_person_id=teacher.id)
    db.add(klass)
    db.flush()
    student = Person(
        password_hash=hash_password("123456"),
        payload=validate_person_payload("student", {"name": "林小明", "admission_no": "S1"}),
    )
    db.add(student)
    db.flush()
    db.add(Enrollment(person_id=student.id, class_id=klass.id,
                      valid_from=date(2025, 9, 1)))
    _seed_token(db, teacher2, TEACHER2_TOKEN)
    _seed_token(db, teacher, TEACHER_TOKEN)
    _seed_token(db, admin_p, ADMIN_TOKEN)
    db.commit()
    ids = {
        "admin": str(admin_p.id),
        "teacher": str(teacher.id),
        "teacher2": str(teacher2.id),
        "student": str(student.id),
    }

    tc.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
    yield tc, ids
    tc.headers.clear()


def _as(tc, token: str) -> None:
    tc.headers.update({"Authorization": f"Bearer {token}"})


def test_non_admin_cannot_access_admin_users(client):
    tc, _ = client
    _as(tc, TEACHER_TOKEN)
    assert tc.get("/api/admin/users").status_code == 403
    assert tc.get("/api/admin/stats").status_code == 403


def test_admin_lists_users_with_role_filter(client):
    tc, ids = client
    body = tc.get("/api/admin/users").json()
    # Students are persons too now, so the unfiltered list shows every role.
    assert {u["role"] for u in body} == {"admin", "teacher", "student"}
    assert len(body) == 4
    assert {u["id"] for u in body} == set(ids.values())
    assert all(uuid.UUID(u["id"]) for u in body)
    assert {u["name"] for u in body} == {"管理员", "陈老师", "赵老师", "林小明"}
    assert all(u["is_active"] is True for u in body)

    teachers = tc.get("/api/admin/users", params={"role": "teacher"}).json()
    assert {u["id"] for u in teachers} == {ids["teacher"], ids["teacher2"]}
    assert next(u for u in teachers if u["id"] == ids["teacher"])["subject"] == "math"
    assert tc.get("/api/admin/users", params={"role": "boss"}).status_code == 400


def test_patch_role_validation_and_self_demote_guard(client):
    tc, ids = client
    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"role": "boss"}).status_code == 400
    assert tc.patch(f"/api/admin/users/{ids['admin']}",
                    json={"role": "teacher"}).status_code == 400
    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"role": "admin"}).json() == {"ok": True}
    # The role flip rewrote the payload role (subject has no place in an
    # admin payload), keeping the person active.
    row = next(u for u in tc.get("/api/admin/users").json() if u["id"] == ids["teacher"])
    assert row["role"] == "admin"
    assert row["is_active"] is True


def test_patch_toggles_is_active_in_payload(client):
    tc, ids = client
    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"is_active": False}).json() == {"ok": True}
    row = next(u for u in tc.get("/api/admin/users").json() if u["id"] == ids["teacher"])
    assert row["is_active"] is False
    # A disabled person is rejected from /me with 403.
    r = tc.get("/api/auth/me", headers={"Authorization": f"Bearer {TEACHER_TOKEN}"})
    assert r.status_code == 403

    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"is_active": True}).json() == {"ok": True}
    r = tc.get("/api/auth/me", headers={"Authorization": f"Bearer {TEACHER_TOKEN}"})
    assert r.status_code == 200


def test_admin_cannot_deactivate_self(client):
    tc, ids = client
    assert tc.patch(f"/api/admin/users/{ids['admin']}",
                    json={"is_active": False}).status_code == 400


def test_delete_referenced_user_409_and_clean_user_ok(client, db):
    tc, ids = client
    r = tc.delete(f"/api/admin/users/{ids['teacher']}")  # homeroom + enrollment
    assert r.status_code == 409
    # The 409 guard must leave the person intact.
    db.expire_all()
    assert db.get(Person, uuid.UUID(ids["teacher"])) is not None

    r = tc.delete(f"/api/admin/users/{ids['teacher2']}")  # profile-bearing, evidence-free
    assert r.json() == {"ok": True}
    # The person — and their owned auth sessions — must really be gone.
    db.expire_all()
    assert db.get(Person, uuid.UUID(ids["teacher2"])) is None
    assert db.get(AuthSession, TEACHER2_TOKEN) is None


def test_stats_keys(client, db):
    tc, _ = client
    # A disabled person must not count as active. SQLite's json_extract maps
    # JSON booleans to integers, so SQL text comparisons can't express this —
    # the endpoint counts in Python; this locks that.
    _seed_person(db, "13600000003", name="已停用", active=False)
    db.commit()
    stats = tc.get("/api/admin/stats").json()
    assert set(stats) == {"database", "tables", "users_total", "users_admins",
                          "users_active", "sessions_active"}
    assert stats["users_total"] == 5
    assert stats["users_admins"] == 1
    assert stats["users_active"] == 4  # excludes the disabled teacher
    assert stats["sessions_active"] == 3
    assert stats["tables"]["person"] == 5
    assert "user" not in stats["tables"]
    assert "teacher_profile" not in stats["tables"]
