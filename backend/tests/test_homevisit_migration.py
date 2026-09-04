"""Tests for the StudentEvent generic-record model (former HomeVisit table).

The dedicated home_visit table was dropped in migration 0002; home visits (and
talks / calls / tutoring / notes) all live in student_event. These tests pin
the StudentEvent-based contracts:
  1. the student detail payload no longer carries the legacy `home_visits` key
     — events are served generically via the timeline endpoint;
  2. the timeline lists every event regardless of type;
  3. DELETE falls back to soft-deactivate when teacher-written records exist.
"""

import os

# Use SHARED in-memory SQLite URI so every Engine/connection sees the same DB.
# StaticPool keeps a single underlying sqlite connection alive.
from unittest.mock import patch

_TEST_DB_URI = "sqlite:///file:homevisit_tests?mode=memory&cache=shared&uri=true"
os.environ["DATABASE_URL"] = _TEST_DB_URI


from datetime import datetime  # noqa: E402 (env must be set before any app import)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# App imports (after env is set)
from app.database import Base, get_db  # noqa: E402
from app.events import add_event  # noqa: E402
from app.main import app as raw_app  # noqa: E402
from app.models import (  # noqa: E402
    AuthSession, Class, Enrollment, Student, StudentEvent, User,
)
from app.security import hash_password  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures — single shared SQLite connection for every test
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_engine():
    eng = create_engine(
        _TEST_DB_URI,
        future=True,
        poolclass=StaticPool,              # one sqlite connection for ALL binds
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)

    # Global patch: replace the imported module-level engine & SessionLocal
    # so routers / deps / models that reach around get_db still hit the test DB.
    import app.database as db_mod
    with patch.object(db_mod, "engine", eng), \
         patch.object(db_mod, "SessionLocal", sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)):
        yield eng

    Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def session(test_engine):
    factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture()
def seeded(session):
    """One student with 2 home_visited events + 1 note, all via add_event()."""
    chen = User(name="陈老师", phone="13800000001",
                password_hash=hash_password("123456"), role="teacher")
    session.add(chen); session.flush()

    c1 = Class(name="七年级1班", grade_level=7, academic_year=2026,
               homeroom_teacher_id=chen.id)
    session.add(c1); session.flush()

    lin = Student(admission_no="S001", name="林晓雨", gender="female",
                  status="active",
                  guardian_name="林爸爸", guardian_phone="13810001000")
    session.add(lin); session.flush()
    session.add(Enrollment(student_id=lin.id, class_id=c1.id,
                           valid_from=datetime(2026, 2, 20).date(),
                           valid_to=None, reason="入学"))

    add_event(session, lin.id, "home_visited",
              datetime(2026, 3, 15, 19, 0),
              actor_teacher_id=chen.id,
              payload={"purpose": "开学家访",
                       "summary": "父母工作忙，主要由外婆照顾，已告知学习重点。",
                       "follow_up_needed": True,
                       "follow_up_note": "两周后回访是否落实课外阅读。"})
    add_event(session, lin.id, "home_visited",
              datetime(2026, 5, 10, 19, 30),
              actor_teacher_id=chen.id,
              payload={"purpose": "数学提升计划",
                       "summary": "分数专项练习计划约定，家长已签字。",
                       "follow_up_needed": False,
                       "follow_up_note": None})
    add_event(session, lin.id, "note_added",
              datetime(2026, 4, 20, 15, 0),
              actor_teacher_id=chen.id,
              payload={"note": "对多步骤分数应用题掌握不牢"})

    tok = "t" * 64
    session.add(AuthSession(token=tok, user_id=chen.id))

    session.commit()
    return {"chen": chen, "lin": lin, "token": tok, "c1": c1}


@pytest.fixture()
def client(test_engine, session):
    """FastAPI TestClient. get_db yields the SAME session fixture."""
    def _get_db_override():
        yield session
    raw_app.dependency_overrides[get_db] = _get_db_override
    with TestClient(raw_app) as c:
        yield c
    raw_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TEST 1: 学生详情不再携带旧的家访专用字段 — 事件统一走 timeline
# ---------------------------------------------------------------------------

def test_student_detail_has_no_legacy_home_visits_key(client, seeded):
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.get(f"/api/students/{seeded['lin'].id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "home_visits" not in body, (
        "home_visits was the dedicated-table shape; events are served "
        "generically via /students/{id}/timeline — the legacy key must go.")


# ---------------------------------------------------------------------------
# TEST 2: timeline 通用地列出所有类型的事件（含家访与随笔）
# ---------------------------------------------------------------------------

def test_timeline_lists_all_event_types_generically(client, seeded):
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.get(f"/api/students/{seeded['lin'].id}/timeline", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    types = [it["event_type"] for it in items]
    assert types.count("home_visited") == 2
    assert types.count("note_added") == 1
    assert all(it["is_system"] is False for it in items), (
        "teacher-written records must not be flagged as system events")


# ---------------------------------------------------------------------------
# TEST 3: 首页待跟进卡片 — 任何类型的事件带 follow_up_needed 都要出现
# （回归：SQLite 的 LIKE contains() 曾永远匹配不到嵌套键，卡片恒为空）
# ---------------------------------------------------------------------------

def test_dashboard_follow_ups_lists_events_needing_follow_up(client, seeded):
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.get("/api/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    fu = body["follow_ups"]
    assert len(fu) == 1, f"Expected the 开学家访 follow-up, got {body['follow_ups']}"
    assert fu[0]["student_id"] == seeded["lin"].id
    assert fu[0]["event_type"] == "home_visited"
    assert fu[0]["follow_up_note"] == "两周后回访是否落实课外阅读。"
    # counts.interactions counts every teacher-written record (2 visits + 1 note)
    assert body["counts"]["interactions"] == 3


# ---------------------------------------------------------------------------
# TEST 4: DELETE — 有教师手写记录（家访等）时 → 软删除（停用）
# ---------------------------------------------------------------------------

def test_delete_student_with_manual_records_does_soft_deactivate(client, seeded, session):
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.delete(f"/api/students/{seeded['lin'].id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["action"] == "deactivated", (
        f"Expected action='deactivated' because the student has teacher-written "
        f"records. Got action={body['action']}.")

    # Verify: student record still exists, status is inactive
    s = session.get(Student, seeded["lin"].id)
    assert s is not None
    assert s.status == "inactive"

    # Verify: event rows still exist (append-only log preserved).
    # The soft-delete itself ALSO appends a new note_added event ("账号停用"),
    # so total = 2 visits + 1 study note + 1 deactivation note = 4.
    cnt = (session.query(StudentEvent)
           .filter(StudentEvent.student_id == seeded["lin"].id).count())
    assert cnt == 4, (
        f"Event rows should survive soft-delete + new 'deactivated' note appended. "
        f"Expected 4 (2 visits + 1 note + 1 deactivation note), got {cnt}.")


# ---------------------------------------------------------------------------
# TEST 5: DELETE — 无任何证据时 → 硬删除
# ---------------------------------------------------------------------------

def test_delete_student_without_any_evidence_does_hard_delete(client, seeded, session):
    """Create a clean student with zero business rows. Delete → action: deleted"""
    # Add bare student
    clean = Student(admission_no="S999", name="无历史同学", gender="male", status="active")
    session.add(clean); session.commit()

    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.delete(f"/api/students/{clean.id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["action"] == "deleted", (
        f"Expected action='deleted' for student with no evidence. Got {body['action']}"
    )
    assert session.get(Student, clean.id) is None, "Hard-deleted student must be gone"
