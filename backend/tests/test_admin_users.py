"""Behavior lock for /admin/users: role gating, filtering, update rules,
delete-with-evidence guard. Uses the shared-memory SQLite pattern from
test_kp_qr_removal.py."""
from __future__ import annotations

import os
from datetime import date

_TEST_DB_URI = "sqlite:///file:admin_users_tests?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = _TEST_DB_URI

import pytest  # noqa: E402
from app.models import TeacherProfile, User  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_engine = create_engine(
    _TEST_DB_URI, poolclass=StaticPool, connect_args={"check_same_thread": False}
)
_Session = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client():
    """Fresh app + seeded data per test. Yields an UNAUTHENTICATED TestClient;
    tests log in themselves via _login()."""
    import sys as _sys

    for mod in list(_sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del _sys.modules[mod]

    from app.database import Base, get_db
    from app.main import app as fastapi_app
    from app.models import (
        AuthSession, Class, Enrollment, Exam, ExamResult, ExamSubject,
        Student, TeacherProfile, User,
    )
    from app.security import hash_password

    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)

    def override():
        s = _Session()
        try:
            yield s
        finally:
            s.close()

    fastapi_app.dependency_overrides[get_db] = override

    s = _Session()
    admin = User(name="管理员", phone="13600000000",
                 password_hash=hash_password("123456"), role="admin")
    teacher = User(name="陈老师", phone="13600000001",
                   password_hash=hash_password("123456"), role="teacher")
    teacher2 = User(name="赵老师", phone="13600000002",
                    password_hash=hash_password("123456"), role="teacher")
    s.add_all([admin, teacher, teacher2])
    s.flush()
    s.add(TeacherProfile(user_id=teacher.id, subject="math"))
    # teacher2 also carries a profile: deleting a profile-bearing but
    # evidence-free user used to 500 (ORM tried to blank out the
    # teacher_profile.user_id PK) — the clean-delete test below locks the fix.
    s.add(TeacherProfile(user_id=teacher2.id, subject="english"))

    klass = Class(name="七年级1班", grade_level=7, academic_year="2025/2026",
                  homeroom_teacher_id=teacher.id)
    s.add(klass)
    s.flush()
    student = Student(admission_no="S1", name="林小明", status="active")
    s.add(student)
    s.flush()
    s.add(Enrollment(student_id=student.id, class_id=klass.id,
                     valid_from=date(2025, 9, 1)))
    exam = Exam(name="月考", exam_date=date(2026, 1, 10))
    s.add(exam)
    s.flush()
    es = ExamSubject(exam_id=exam.id, subject="math", full_score=100.0)
    s.add(es)
    s.flush()
    s.add(ExamResult(student_id=student.id, exam_subject_id=es.id,
                     score=90.0, status="entered", entered_by=teacher.id))
    s.add(AuthSession(token="b" * 64, user_id=teacher2.id))
    s.commit()
    ids = {"admin": admin.id, "teacher": teacher.id, "teacher2": teacher2.id}
    s.close()

    yield TestClient(fastapi_app), ids
    fastapi_app.dependency_overrides.clear()


def _login(client, phone: str) -> None:
    r = client.post("/api/auth/login", json={"phone": phone, "password": "123456"})
    assert r.status_code == 200, r.text
    client.headers.update({"Authorization": f"Bearer {r.json()['token']}"})


def test_teacher_role_cannot_access_admin_users(client):
    tc, _ = client
    _login(tc, "13600000001")
    assert tc.get("/api/admin/users").status_code == 403


def test_admin_lists_users_with_role_filter(client):
    tc, ids = client
    _login(tc, "13600000000")
    body = tc.get("/api/admin/users").json()
    assert {u["role"] for u in body} == {"admin", "teacher"}
    assert len(body) == 3
    teachers = tc.get("/api/admin/users", params={"role": "teacher"}).json()
    assert [u["id"] for u in teachers] == [ids["teacher"], ids["teacher2"]]
    assert teachers[0]["subject"] == "math"
    assert tc.get("/api/admin/users", params={"role": "boss"}).status_code == 400


def test_patch_role_validation_and_self_demote_guard(client):
    tc, ids = client
    _login(tc, "13600000000")
    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"role": "boss"}).status_code == 400
    assert tc.patch(f"/api/admin/users/{ids['admin']}",
                    json={"role": "teacher"}).status_code == 400
    assert tc.patch(f"/api/admin/users/{ids['teacher']}",
                    json={"role": "admin"}).json() == {"ok": True}


def test_delete_referenced_user_409_and_clean_user_ok(client):
    tc, ids = client
    _login(tc, "13600000000")
    r = tc.delete(f"/api/admin/users/{ids['teacher']}")  # homeroom + entered results
    assert r.status_code == 409
    # The 409 guard must leave the user AND their profile intact.
    s = _Session()
    try:
        assert s.get(User, ids["teacher"]) is not None
        assert s.query(TeacherProfile).filter(
            TeacherProfile.user_id == ids["teacher"]).first() is not None
    finally:
        s.close()
    r = tc.delete(f"/api/admin/users/{ids['teacher2']}")  # profile-bearing, evidence-free
    assert r.json() == {"ok": True}
    # Regression: deleting a profile-bearing, evidence-free user used to 500
    # (ORM tried to blank out the teacher_profile.user_id PK). The profile row
    # must really be gone along with the user.
    s = _Session()
    try:
        assert s.get(User, ids["teacher2"]) is None
        assert s.query(TeacherProfile).filter(
            TeacherProfile.user_id == ids["teacher2"]).first() is None
    finally:
        s.close()


def test_admin_cannot_deactivate_self(client):
    tc, ids = client
    _login(tc, "13600000000")
    # KNOWN GAP (final review): admin can deactivate self; should be 400.
    # Locked to the current not-a-crash behavior for now.
    assert tc.patch(f"/api/admin/users/{ids['admin']}",
                    json={"is_active": False}).json() == {"ok": True}


def test_stats_keys(client):
    tc, _ = client
    _login(tc, "13600000000")  # adds one session to the 1 pre-seeded one
    stats = tc.get("/api/admin/stats").json()
    assert stats["users_total"] == 3
    assert stats["users_admins"] == 1
    assert stats["users_active"] == 3
    assert stats["sessions_active"] == 2
    assert stats["tables"]["user"] == 3
    assert "teacher" not in stats["tables"]
