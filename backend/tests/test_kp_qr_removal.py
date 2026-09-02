"""TDD tests for removing KnowledgePoint / Question / QuestionResponse /
StudentWeakness tables and all dependent logic.

Run:
  cd backend && ./.venv/bin/python -m pytest tests/test_kp_qr_removal.py -v
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


# Shared in-memory SQLite so the app + tests see the same tables.
DB_URI = "sqlite:///file:kpqr_tests?mode=memory&cache=shared&uri=true"


@contextmanager
def _patched_app():
    """Patch the app's database engine/session, seed, return a TestClient."""
    os.environ["DATABASE_URL"] = DB_URI

    # Force-reimport modules with the new env.
    import sys as _sys

    for mod in list(_sys.modules.keys()):
        if mod.startswith("app.") or mod in ("app",):
            del _sys.modules[mod]

    from app.database import Base, get_db
    from app.main import app as fastapi_app
    from app.security import hash_password

    engine = create_engine(DB_URI, poolclass=StaticPool, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    # ---- Seed a minimum set required to hit every endpoint we test ----
    db: Session = TestingSessionLocal()
    try:
        from app.models import (
            AuthSession,
            Class,
            Enrollment,
            Exam,
            ExamResult,
            ExamSubject,
            Student,
            StudentEvent,
            Teacher,
        )

        # 1 admin + 1 teacher
        admin = Teacher(
            name="Super Admin",
            phone="10000000001",
            email="admin@example.com",
            password_hash=hash_password("123456"),
            is_admin=True,
        )
        teacher = Teacher(
            name="Ms. Chen",
            phone="10000000002",
            email="chen@example.com",
            password_hash=hash_password("123456"),
            subject="语文",
            is_admin=False,
        )
        db.add_all([admin, teacher])
        db.flush()

        klass = Class(
            name="七年级1班",
            grade_level=7,
            academic_year="2025-2026",
            homeroom_teacher_id=teacher.id,
        )
        db.add(klass)
        db.flush()

        from datetime import date as _date

        student = Student(
            admission_no="S001",
            name="林小明",
            gender="男",
            birth_date=_date(2013, 5, 1),
            guardian_name="林先生",
            guardian_phone="13800000000",
            address="北京市",
            status="active",
        )
        db.add(student)
        db.flush()
        db.add(Enrollment(student_id=student.id, class_id=klass.id, valid_from=_date(2025, 9, 1)))

        # 1 exam + subject + result  (so delete_student has evidence)
        exam = Exam(name="月考1", exam_date=_date(2026, 1, 10))
        db.add(exam)
        db.flush()
        es = ExamSubject(exam_id=exam.id, subject="语文", full_score=100.0)
        db.add(es)
        db.flush()
        db.add(
            ExamResult(
                student_id=student.id,
                exam_subject_id=es.id,
                score=85.0,
                status="entered",
                entered_by=teacher.id,
            )
        )

        # 2 home_visited events + 1 note (used by the "does soft deactivate" test)
        from datetime import datetime as _dt
        from app.events import add_event

        add_event(
            db, student.id, "home_visited", _dt(2026, 1, 20, 15, 0),
            actor_teacher_id=teacher.id,
            payload={"purpose": "常规家访", "summary": "表现良好", "follow_up_needed": False},
        )
        add_event(
            db, student.id, "home_visited", _dt(2026, 2, 20, 16, 0),
            actor_teacher_id=teacher.id,
            payload={"purpose": "跟进", "summary": "持续关注", "follow_up_needed": True, "follow_up_note": "下周电联"},
        )
        add_event(
            db, student.id, "note_added", _dt(2026, 3, 1, 9, 0),
            actor_teacher_id=teacher.id,
            payload={"note": "本周参加竞赛"},
        )

        # Two bearer sessions
        tok_admin = "tt_admin_" + "a" * 48
        tok_teacher = "tt_tch_" + "b" * 48
        db.add(AuthSession(token=tok_admin, teacher_id=admin.id))
        db.add(AuthSession(token=tok_teacher, teacher_id=teacher.id))

        db.commit()
    finally:
        db.close()

    try:
        yield fastapi_app, TestingSessionLocal, tok_admin, tok_teacher
    finally:
        fastapi_app.dependency_overrides.clear()


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def app_fixture():
    with _patched_app() as (app, sess_local, tok_admin, tok_teacher):
        sess = sess_local()
        try:
            yield TestClient(app), sess, tok_admin, tok_teacher, sess_local
        finally:
            sess.close()


# ---------- Tests ----------

def test_models_no_kp_q_qr_sw(app_fixture):
    """AC: KnowledgePoint / Question / QuestionResponse / StudentWeakness are
    completely removed from app.models module (import + attribute check)."""
    import app.models as m
    missing = []
    for name in ("KnowledgePoint", "Question", "QuestionResponse", "StudentWeakness"):
        if hasattr(m, name):
            missing.append(name)
    assert missing == [], (
        f"Expected 4 legacy classes removed from models.py, still found: {missing}"
    )


def test_metadata_tables_excludes_legacy(app_fixture):
    """AC: Base.metadata.tables has no rows for the 4 legacy tables."""
    from app.database import Base
    tables = set(Base.metadata.tables.keys())
    legacy = {"knowledge_point", "question", "question_response", "student_weakness"}
    overlap = tables & legacy
    assert overlap == set(), f"Legacy tables still present in Base.metadata: {overlap}"


def test_weaknesses_route_removed_404(app_fixture):
    """AC: GET /api/students/{id}/weaknesses returns 404 (endpoint deleted)."""
    client, sess, tok_admin, tok_teacher, _ = app_fixture
    from app.models import Student
    st_id = sess.query(Student).first().id
    r = client.get(
        f"/api/students/{st_id}/weaknesses",
        headers={"Authorization": f"Bearer {tok_teacher}"},
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_failed_questions_route_removed_404(app_fixture):
    """AC: GET /api/students/{id}/failed-questions returns 404."""
    client, sess, tok_admin, tok_teacher, _ = app_fixture
    from app.models import Student
    st_id = sess.query(Student).first().id
    r = client.get(
        f"/api/students/{st_id}/failed-questions?subject=语文",
        headers={"Authorization": f"Bearer {tok_teacher}"},
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


def test_delete_student_without_qr_sw_still_soft_deactivates(app_fixture):
    """AC: After removing QuestionResponse/StudentWeakness tables, delete-student
    still soft-deactivates when there is other evidence (ExamResult + home
    visited events). Status -> inactive + 1 extra note_added event."""
    client, sess, tok_admin, tok_teacher, SessLocal = app_fixture
    from app.models import Student, StudentEvent
    st = sess.query(Student).first()
    before_events = sess.query(StudentEvent).filter(StudentEvent.student_id == st.id).count()
    r = client.delete(
        f"/api/students/{st.id}",
        headers={"Authorization": f"Bearer {tok_teacher}"},
    )
    assert r.status_code == 200, f"Unexpected {r.status_code}: {r.text}"

    # Re-fetch via a fresh session to avoid stale data.
    sess2 = SessLocal()
    try:
        st2 = sess2.get(Student, st.id)
        assert st2 is not None, "Student was hard-deleted but should have been soft-inactivated (ExamResult + home_visits evidence)."
        assert st2.status == "inactive", f"Expected status=inactive, got {st2.status!r}"
        after_events = sess2.query(StudentEvent).filter(StudentEvent.student_id == st.id).count()
        # before: 2 home_visited + 1 note = 3; after soft-delete: +1 note_added "账号停用" => 4
        assert after_events == before_events + 1, (
            f"Expected {before_events}+1 events after soft deactivation, got {after_events}"
        )
    finally:
        sess2.close()


def test_seed_no_question_response_data(app_fixture):
    """AC: After seeding, no QuestionResponse / KnowledgePoint data can exist
    (the tables should be gone entirely — confirm the DB-level tables also
    don't exist via raw PRAGMA/SQL)."""
    _, sess, *_ = app_fixture
    # SQLite: check sqlite_master for legacy tables
    rows = sess.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('knowledge_point','question','question_response','student_weakness')")).fetchall()
    assert rows == [], f"Legacy physical tables still exist in DB: {rows}"


def test_admin_stats_allowlist_does_not_include_legacy_tables(app_fixture):
    """AC: /admin/stats table-count keys should NOT include the 4 legacy names."""
    client, sess, tok_admin, *_ = app_fixture
    r = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {tok_admin}"})
    assert r.status_code == 200, r.text
    data = r.json()
    legacy = {"knowledge_point", "question", "question_response", "student_weakness"}
    overlap = set(data.get("tables", {}).keys()) & legacy
    assert overlap == set(), f"/admin/stats tables still lists legacy: {overlap}"


def test_admin_inspect_legacy_table_returns_400(app_fixture):
    """AC: /admin/inspect for any legacy table name returns 400 '未知数据表'."""
    client, sess, tok_admin, *_ = app_fixture
    for tbl in ("knowledge_point", "question", "question_response", "student_weakness"):
        r = client.post(
            "/api/admin/inspect",
            json={"table": tbl, "limit": 5},
            headers={"Authorization": f"Bearer {tok_admin}"},
        )
        assert r.status_code == 400, f"table={tbl}: Expected 400, got {r.status_code}: {r.text}"
