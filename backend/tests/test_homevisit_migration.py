"""TDD tests for migrating HomeVisit table usage → StudentEvent event_type='home_visited'.

These tests MUST FAIL on the current codebase (RED state) because:
  1. get_student() queries HomeVisit table (empty in seed/prod), not StudentEvent.
  2. delete_student() checks HomeVisit for evidence, not event_type='home_visited' rows.

After migration (GREEN state), all tests pass.
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
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# App imports (after env is set)
from app.database import Base, get_db  # noqa: E402
from app.events import add_event  # noqa: E402
from app.main import app as raw_app  # noqa: E402
from app.models import (  # noqa: E402
    AuthSession, Class, Enrollment, Exam, ExamResult, ExamSubject,
    Student, StudentEvent, Teacher,
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
    """Seed just enough data for home_visit related assertions.

    IMPORTANT: We intentionally write NO rows into the legacy `HomeVisit` table.
    Everything flows via add_event(..., "home_visited", ...) — the real path.
    """
    # 1 教师
    chen = Teacher(name="陈老师", phone="13800000001",
                   password_hash=hash_password("123456"), is_admin=False)
    session.add(chen); session.flush()

    # 1 班级
    c1 = Class(name="七年级1班", grade_level=7, academic_year=2026,
               homeroom_teacher_id=chen.id)
    session.add(c1); session.flush()

    # 1 学生 + enrollment
    lin = Student(admission_no="S001", name="林晓雨", gender="female",
                  status="active",
                  guardian_name="林爸爸", guardian_phone="13810001000")
    session.add(lin); session.flush()
    session.add(Enrollment(student_id=lin.id, class_id=c1.id,
                           valid_from=datetime(2026, 2, 20).date(),
                           valid_to=None, reason="入学"))

    # 2 次 home_visited 事件（走 StudentEvent.events.py 追加式写入）
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

    # 1 条非家访事件，确保 home_visits 不会误把它算进来
    add_event(session, lin.id, "note_added",
              datetime(2026, 4, 20, 15, 0),
              actor_teacher_id=chen.id,
              payload={"note": "对多步骤分数应用题掌握不牢"})

    # Auth session for Teacher Chen → Bearer Token
    tok = "t" * 64
    session.add(AuthSession(token=tok, teacher_id=chen.id))

    session.commit()
    return {"chen": chen, "lin": lin, "token": tok, "c1": c1}


@pytest.fixture()
def client(test_engine, session):
    """FastAPI TestClient. get_db yields the SAME session fixture.
    We also patch the engine module-wide so code paths beyond Depends(get_db)
    (e.g., model reflection in create_all) stay consistent."""
    def _get_db_override():
        yield session
    raw_app.dependency_overrides[get_db] = _get_db_override
    with TestClient(raw_app) as c:
        yield c
    raw_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TEST 1: GET /api/students/{id}  home_visits 字段应来自 StudentEvent
# ---------------------------------------------------------------------------

def test_student_detail_home_visits_populated_from_student_event(client, seeded):
    """RED 状态下当前代码会返回 home_visits: [] （空数组），
    因为它查的是空的 HomeVisit 表，不查 StudentEvent。"""
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.get(f"/api/students/{seeded['lin'].id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    visits = body["home_visits"]
    # FAIL EXPECTED: current code returns [] (querying HomeVisit table)
    # PASS EXPECTED: 2 visits from the home_visited events
    assert len(visits) == 2, (
        f"Expected 2 home_visits from StudentEvent, got {len(visits)}. "
        f"Raw: {visits}. "
        f"— Bug: get_student() still reads legacy HomeVisit table, not StudentEvent."
    )

    # Check the visits are chronologically DESC (newest first, as current API spec)
    # May 10 should come before March 15
    assert visits[0]["purpose"] == "数学提升计划"
    assert visits[1]["purpose"] == "开学家访"

    # Field mapping fidelity: each payload field must map to the correct dict key
    first = visits[1]  # earlier = 开学家访
    assert first["summary"] == "父母工作忙，主要由外婆照顾，已告知学习重点。"
    assert first["follow_up_needed"] is True
    assert first["follow_up_note"] == "两周后回访是否落实课外阅读。"
    assert "visited_at" in first and first["visited_at"].startswith("2026-03-15")

    # Every home_visits[] item MUST carry its source StudentEvent id
    # so the frontend can hyperlink (currently unused but critical for API stability)
    for v in visits:
        assert isinstance(v["id"], int) and v["id"] > 0, (
            "home_visits[].id should be the backing StudentEvent id")


# ---------------------------------------------------------------------------
# TEST 2: note_added 事件不出现在 home_visits 中
# ---------------------------------------------------------------------------

def test_student_detail_home_visits_excludes_other_event_types(client, seeded):
    """Only event_type == 'home_visited' counts toward the home_visits array."""
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.get(f"/api/students/{seeded['lin'].id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    purposes = {v.get("purpose") for v in body["home_visits"]}
    assert "数学提升计划" in purposes
    assert "开学家访" in purposes
    # There should be no "note_added" masquerading as a home_visit (via id 3 note event)
    summaries = [v.get("summary") for v in body["home_visits"]]
    for s in summaries:
        assert s != "对多步骤分数应用题掌握不牢"


# ---------------------------------------------------------------------------
# TEST 3: DELETE /api/students/{id}  有 home_visited 事件证据时 → 软删除（停用）
# ---------------------------------------------------------------------------

def test_delete_student_with_home_visited_events_does_soft_deactivate(client, seeded, session):
    """RED 状态下：delete_student() 查的是 HomeVisit（空），
    所以它会硬删 student，而不是走 soft-deactivate 分支。

    期望：存在 home_visited 事件时 → action: 'deactivated'（软删）。
    """
    headers = {"Authorization": f"Bearer {seeded['token']}"}
    r = client.delete(f"/api/students/{seeded['lin'].id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["action"] == "deactivated", (
        f"Expected action='deactivated' because student has home_visited evidence. "
        f"Got action={body['action']}. "
        f"— Bug: delete_student() checks HomeVisit table instead of "
        f"StudentEvent(event_type='home_visited') for written evidence."
    )

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
# TEST 4: DELETE /api/students/{id}  无任何证据时 → 硬删除
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
