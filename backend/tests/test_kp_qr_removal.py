"""Regression guards for the legacy-schema removals.

The original file pinned the KnowledgePoint / Question / QuestionResponse /
StudentWeakness removal; after the event-schema migration the same guards
extend to the whole legacy identity/exam schema:

  1. legacy model names (Student, StudentEvent, User, Exam, ExamResult,
     TeacherProfile, add_event) are not importable from the app.models
     package, and app.events (the legacy add_event helper module) is gone;
  2. the new names (Person, Event, AuthSession) are importable;
  3. no legacy tables survive in Base.metadata or the physical DB;
  4. the removed /weaknesses + /failed-questions routes still 404 on the
     full app (ported — the routes must stay gone);
  5. delete-student still soft-deactivates when the student has evidence
     (ported — now: score/record Events instead of ExamResults);
  6. /admin/stats never lists legacy tables and /admin/inspect rejects them.

Runs against the full app.main client (conftest `client` fixture) with
get_db on the same throwaway SQLite engine as the `db` fixture.
"""
import pytest
from sqlalchemy import text

from tests.conftest import seed_person, seed_token

# Every pre-event-schema table name: the KP/QR removal era plus the
# identity/exam tables the event schema replaced (see alembic 0001-0004).
LEGACY_TABLES = {
    # KP/QR removal
    "knowledge_point", "question", "question_response", "student_weakness",
    # legacy identity + exam schema
    "user", "teacher", "teacher_profile", "student", "student_event",
    "exam", "exam_subject", "exam_result", "home_visit", "student_tag",
}

TEACHER_TOKEN = "t" * 64
ADMIN_TOKEN = "a" * 64


def test_legacy_names_not_importable_from_models():
    """Legacy models and the add_event helper must not sneak back into
    app.models, and app.events must stay deleted."""
    import app.models as m

    leaked = [
        name for name in (
            "Student", "StudentEvent", "User", "Exam", "ExamResult",
            "TeacherProfile", "add_event",
        )
        if hasattr(m, name)
    ]
    assert leaked == [], f"legacy names importable from app.models: {leaked}"

    with pytest.raises(ModuleNotFoundError):
        import app.events  # noqa: F401


def test_new_schema_names_importable():
    from app.models import AuthSession, Event, Person  # noqa: F401


def test_no_legacy_tables_in_metadata_or_db(engine):
    from app.database import Base

    overlap = set(Base.metadata.tables) & LEGACY_TABLES
    assert overlap == set(), f"legacy tables registered on Base.metadata: {overlap}"

    # physical check: create_all'd test DB has no legacy tables either
    with engine.connect() as conn:
        names = {name for (name,) in conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'"))}
    assert names & LEGACY_TABLES == set(), f"legacy tables exist in DB: {names & LEGACY_TABLES}"


def _seed_student_with_evidence(db):
    """A student with a class + a teacher-written record: enough evidence
    that delete must soft-deactivate rather than hard-delete."""
    from datetime import date, datetime

    from app import eventing
    from app.models import Class, Enrollment

    teacher = seed_person(db, "chen139@test.example", phone="13900000001", name="陈老师")
    seed_token(db, teacher, TEACHER_TOKEN)
    student = seed_person(db, None, role="student", name="林小明", admission_no="S901")
    klass = Class(name="七年级1班", academic_year="2025/2026")
    db.add(klass)
    db.flush()
    db.add(Enrollment(person_id=student.id, class_id=klass.id, valid_from=date(2025, 9, 1)))
    eventing.create_event(db, event_type="home_visited", title="家访",
                          start_time=datetime(2026, 3, 20, 19, 0),
                          payload={"summary": "常规家访"},
                          attendee_ids=[student.id])
    db.commit()
    return teacher, student


def test_removed_weakness_and_failed_question_routes_404(client, db):
    """The KP/QR-era endpoints stay deleted on the full app."""
    _, student = _seed_student_with_evidence(db)
    headers = {"Authorization": f"Bearer {TEACHER_TOKEN}"}
    assert client.get(f"/api/students/{student.id}/weaknesses", headers=headers).status_code == 404
    r = client.get(f"/api/students/{student.id}/failed-questions",
                   params={"subject": "语文"}, headers=headers)
    assert r.status_code == 404


def test_delete_student_with_evidence_soft_deactivates(client, db):
    """Deleting a student that has written evidence keeps the person and
    flips is_active off + logs a 停用 note (was: ExamResult/home-visit
    evidence; now score/record Events are the evidence)."""
    from app.models import Enrollment, Event, Person

    _, student = _seed_student_with_evidence(db)
    before = db.query(Event).filter(Event.attendees.any(Person.id == student.id)).count()

    r = client.delete(f"/api/students/{student.id}",
                      headers={"Authorization": f"Bearer {TEACHER_TOKEN}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "action": "deactivated"}

    db.expire_all()
    st = db.get(Person, student.id)
    assert st is not None, "student was hard-deleted despite having evidence"
    assert (st.payload or {}).get("is_active") is False
    # +1 comment ("账号停用") on the timeline; enrollments closed
    after = db.query(Event).filter(Event.attendees.any(Person.id == student.id)).count()
    assert after == before + 1
    note = (
        db.query(Event)
        .filter(Event.type == "comment", Event.attendees.any(Person.id == student.id))
        .order_by(Event.start_time.desc())
        .first()
    )
    assert note.title == "账号停用"
    assert note.payload["notes"] == "账号停用"
    assert all(e.valid_to is not None for e in db.query(Enrollment)
               .filter(Enrollment.person_id == student.id).all())


@pytest.fixture()
def admin_client(client, db):
    """Full-app client with an admin Authorization header pre-set."""
    admin = seed_person(db, "admin139@test.example", phone="13900000000",
                        role="admin", name="管理员")
    seed_token(db, admin, ADMIN_TOKEN)
    client.headers.update({"Authorization": f"Bearer {ADMIN_TOKEN}"})
    yield client
    client.headers.clear()


def test_admin_stats_excludes_legacy_tables(admin_client, db):
    """/admin/stats counts only the new-schema tables."""
    r = admin_client.get("/api/admin/stats")
    assert r.status_code == 200, r.text
    tables = set(r.json()["tables"])
    assert tables == {"person", "auth_session", "event", "tag", "class", "enrollment"}
    assert not tables & LEGACY_TABLES


def test_admin_inspect_rejects_legacy_tables(admin_client):
    for tbl in sorted(LEGACY_TABLES):
        r = admin_client.post("/api/admin/inspect", json={"table": tbl, "limit": 5})
        assert r.status_code == 400, f"table={tbl}: {r.status_code} {r.text}"
        assert r.json()["detail"] == "未知数据表"
