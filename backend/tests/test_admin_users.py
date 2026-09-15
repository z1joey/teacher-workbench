"""Behavior lock for /admin/users: require_admin gating, role filtering,
update rules, delete-with-evidence guard. Adapted from the User-based file to
Person + payload identities: ids are UUID strings, name lives on the column
and is_active/role/role-attributes live in the payload, and tokens are seeded
directly (make_client replaces the full-app fixture while routers are mid-
migration)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from app.eventing import create_event
from app.models import AuthSession, Class, Enrollment, Event, Person
from app.payloads import validate_person_payload
from app.routers import admin, auth
from app.security import hash_password
from tests.conftest import seed_person, seed_token

ADMIN_TOKEN = "a" * 64
TEACHER_TOKEN = "d" * 64
TEACHER2_TOKEN = "c" * 64


@pytest.fixture()
def client(make_client, db):
    """Fresh app + seeded data per test. Yields (TestClient, ids) with the
    admin token pre-set as Authorization header; tests needing another
    identity swap the header themselves. Admin endpoints carry their own
    require_admin guard, so the app mounts without a global auth dependency
    (exactly like app/main.py does)."""
    tc = make_client(auth.router, admin.router, auth_dependency=False)

    admin_p = seed_person(db, "admin136@test.example", phone="13600000000",
                          role="admin", name="管理员")
    teacher = seed_person(db, "teacher136@test.example", phone="13600000001", name="陈老师")
    teacher2 = seed_person(db, "teacher237@test.example", phone="13600000002", name="赵老师")

    klass = Class(name="七年级1班", academic_year="2025/2026")
    db.add(klass)
    db.flush()
    student = Person(
        name="林小明",
        password_hash=hash_password("123456"),
        payload=validate_person_payload("student", {"admission_no": "S1"}),
    )
    db.add(student)
    db.flush()
    db.add(Enrollment(person_id=student.id, class_id=klass.id,
                      valid_from=date(2025, 9, 1)))
    seed_token(db, teacher2, TEACHER2_TOKEN)
    seed_token(db, teacher, TEACHER_TOKEN)
    seed_token(db, admin_p, ADMIN_TOKEN)
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
    students = tc.get("/api/admin/users", params={"role": "student"}).json()
    assert {u["id"] for u in students} == {ids["student"]}
    assert students[0]["admission_no"] == "S1"
    assert tc.get("/api/admin/users", params={"role": "guardian"}).json() == []
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
    # admin payload), keeping the person active. The name stays on the column.
    row = next(u for u in tc.get("/api/admin/users").json() if u["id"] == ids["teacher"])
    assert row["role"] == "admin"
    assert row["name"] == "陈老师"
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
    # Homeroom links are gone — a teacher with only a class on file can be removed.
    assert tc.delete(f"/api/admin/users/{ids['teacher']}").json() == {"ok": True}
    db.expire_all()
    assert db.get(Person, uuid.UUID(ids["teacher"])) is None

    r = tc.delete(f"/api/admin/users/{ids['teacher2']}")  # profile-bearing, evidence-free
    assert r.json() == {"ok": True}
    # The person — and their owned auth sessions — must really be gone.
    db.expire_all()
    assert db.get(Person, uuid.UUID(ids["teacher2"])) is None
    assert db.get(AuthSession, TEACHER2_TOKEN) is None


def test_patch_student_rejected_and_payload_untouched(client, db):
    """A role change rebuilds the payload from {is_active} only — it
    must never touch a student profile (admission_no/birth_date)."""
    tc, ids = client
    r = tc.patch(f"/api/admin/users/{ids['student']}", json={"role": "teacher"})
    assert r.status_code == 400
    assert r.json()["detail"] == "学生账号不支持此操作"
    db.expire_all()
    row = db.get(Person, uuid.UUID(ids["student"]))
    assert row.payload["role"] == "student"
    assert row.name == "林小明"
    assert row.payload["admission_no"] == "S1"  # not wiped


def test_delete_event_attending_student_rejected(client, db):
    """Hard-deleting an event-attending student would orphan their event rows
    (no enrollment → the 409 evidence guard wouldn't have caught it)."""
    tc, _ = client
    s2 = seed_person(db, None, role="student", name="王小一", admission_no="S99")
    db.flush()
    create_event(
        db, event_type="comment", title="课堂表现活跃",
        start_time=datetime(2026, 5, 1, 10, 0),
        payload={
            "notes": "课堂表现活跃",
            "about": {"id": str(s2.id), "name": s2.name},
        },
        attendee_ids=[s2.id],
    )
    db.commit()

    r = tc.delete(f"/api/admin/users/{s2.id}")
    assert r.status_code == 400
    assert r.json()["detail"] == "学生账号不支持此操作"
    db.expire_all()
    assert db.get(Person, s2.id) is not None
    assert db.query(Event).join(Event.attendees).filter(Person.id == s2.id).count() == 1


def test_stats_keys(client, db):
    tc, _ = client
    # A disabled person must not count as active. SQLite's json_extract maps
    # JSON booleans to integers, so SQL text comparisons can't express this —
    # the endpoint counts in Python; this locks that.
    seed_person(db, "inactive@test.example", phone="13600000003", name="已停用", active=False)
    db.commit()
    stats = tc.get("/api/admin/stats").json()
    assert set(stats) == {
        "database", "tables", "users_total", "persons_total", "accounts_total",
        "users_admins", "users_active", "accounts_active", "sessions_active",
    }
    assert stats["persons_total"] == stats["users_total"] == 5
    assert stats["accounts_total"] == 4  # admin + 2 teachers + inactive teacher
    assert stats["users_admins"] == 1
    assert stats["users_active"] == 4  # all roles, excludes disabled teacher
    assert stats["accounts_active"] == 3  # login roles only, excludes disabled teacher
    assert stats["sessions_active"] == 3
    assert stats["tables"]["person"] == 5
    assert "user" not in stats["tables"]
    assert "teacher_profile" not in stats["tables"]
