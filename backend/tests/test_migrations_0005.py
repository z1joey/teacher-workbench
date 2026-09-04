"""Alembic 0005: legacy schema → event schema data migration.

Runs the REAL chain (command.upgrade "0004" — the legacy schema exactly as
production) against a temp SQLite file, populates every legacy entity via
plain SQL (edge rows included: inactive student, absent result, closed
enrollment, session for an unknown user), then upgrades to 0005 and asserts
every legacy row landed, transformed, where the event schema keeps it.

Two extra guards: downgrade refuses (lossy), and invoking the revision's
upgrade() a second time against the already-migrated database is a no-op
(the legacy "user" table is gone and "person" exists).

DATABASE_URL must not leak in (same discipline as the old
tests/test_migrations.py this file continues).
"""
import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
TOKEN = "f" * 64
GHOST_TOKEN = "z" * 64  # auth_session row pointing at a nonexistent user_id


@pytest.fixture()
def alembic_cfg(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'mig.db'}")
    return cfg


@pytest.fixture()
def db_url(alembic_cfg):
    return alembic_cfg.get_main_option("sqlalchemy.url")


def _seed_legacy(db_url: str) -> None:
    """Insert every legacy entity (one-plus of each) with raw SQL.

    2 users (teacher w/ profile + admin), 2 students (full profile fields,
    one inactive), 1 class w/ homeroom, 2 enrollments (one closed), 1 exam +
    2 exam_subjects + 3 exam_results (one absent), 2 tags + 1 student_tag,
    2 student_events (home_visited + recurring birthday), 2 auth_sessions
    (one for an unknown user — legacy SQLite FKs are unenforced, prod data
    can be just as dirty).
    """
    engine = create_engine(db_url)
    stmts = [
        # users: 1 teacher (with profile) + 1 admin
        'INSERT INTO "user" (id, name, phone, email, password_hash, role, is_active,'
        " created_at) VALUES"
        " (1, '陈老师', '13800000001', 'chen@school.edu', 'hash-teacher', 'teacher',"
        "  1, '2025-09-01 08:00:00'),"
        " (2, '开发者', '13800000000', 'admin@school.dev', 'hash-admin', 'admin',"
        "  1, '2025-09-01 08:00:00')",
        "INSERT INTO teacher_profile (user_id, subject) VALUES (1, 'math')",
        # students: full profile fields; 11 is inactive ("graduated")
        "INSERT INTO student (id, admission_no, name, gender, birth_date,"
        " guardian_name, guardian_phone, address, status, created_at, updated_at)"
        " VALUES"
        " (10, 'S2025001', '林晓雨', 'F', '2012-05-12', '林女士', '13900000001',"
        "  '解放路100号', 'active', '2025-09-01 08:00:00', '2025-09-01 08:00:00'),"
        " (11, 'S2025002', '王浩', 'M', '2012-11-03', '王先生', '13900000002',"
        "  '解放路101号', 'graduated', '2025-09-01 08:00:00', '2026-07-01 10:00:00')",
        # class with homeroom teacher
        "INSERT INTO class (id, name, grade_level, academic_year, homeroom_teacher_id)"
        " VALUES (20, '七年级1班', 7, '2025/2026', 1)",
        # enrollments: 10 current, 11 closed
        "INSERT INTO enrollment (id, student_id, class_id, valid_from, valid_to, reason)"
        " VALUES"
        " (30, 10, 20, '2025-09-01', NULL, 'admitted'),"
        " (31, 11, 20, '2025-09-01', '2026-06-30', 'graduated')",
        # exam + per-subject full scores
        "INSERT INTO exam (id, name, exam_date) VALUES (40, '期中考试', '2025-11-18')",
        "INSERT INTO exam_subject (id, exam_id, subject, full_score) VALUES"
        " (50, 40, 'math', 120.0), (51, 40, 'english', 100.0)",
        # results: 2 entered + 1 absent (absent has score NULL)
        "INSERT INTO exam_result (id, student_id, exam_subject_id, score, status,"
        " entered_by, created_at, updated_at) VALUES"
        " (60, 10, 50, 95.0, 'entered', 1, '2025-11-18 20:00:00', '2025-11-18 20:00:00'),"
        " (61, 10, 51, 88.0, 'entered', 1, '2025-11-18 20:00:00', '2025-11-18 20:00:00'),"
        " (62, 11, 50, NULL, 'absent', 1, '2025-11-18 20:00:00', '2025-11-18 20:00:00')",
        # manual timeline: home visit + recurring birthday (legacy payload is JSON text)
        "INSERT INTO student_event (id, student_id, event_type, occurred_at,"
        " actor_teacher_id, ref_table, ref_id, recurrence, payload) VALUES"
        " (90, 10, 'home_visited', '2026-03-20 19:00:00', 1, NULL, NULL, 'once',"
        '  \'{"title": "家访", "summary": "频繁迟到", "description": "跟进出勤"}\'),'
        " (91, 11, 'birthday', '2025-11-03 08:00:00', NULL, NULL, NULL, 'yearly',"
        '  \'{"title": "生日"}\')',
        # tags: one in use, one orphaned-but-kept
        "INSERT INTO tag (id, name, color) VALUES"
        " (70, '需关注', '#b42318'), (71, '课代表', '#177245')",
        "INSERT INTO student_tag (id, student_id, tag_id) VALUES (80, 10, 70)",
        # sessions: one real, one for an unknown user (must be dropped)
        "INSERT INTO auth_session (token, user_id, created_at) VALUES"
        f" ('{TOKEN}', 1, '2025-12-01 09:00:00'),"
        f" ('{GHOST_TOKEN}', 999, '2025-12-01 09:00:00')",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
    engine.dispose()


def _load_revision():
    """Import 0005_event_schema.py directly (for guard/downgrade checks)."""
    path = BACKEND_DIR / "alembic" / "versions" / "0005_event_schema.py"
    spec = importlib.util.spec_from_file_location("mig_0005_event_schema", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def migrated(alembic_cfg, db_url):
    """Legacy chain 0001→0004, legacy rows, then the 0005 data migration."""
    from alembic import command

    command.upgrade(alembic_cfg, "0004")
    _seed_legacy(db_url)
    command.upgrade(alembic_cfg, "0005")
    return db_url


def test_upgrade_rebuilds_event_schema(migrated):
    import app.models  # noqa: F401  (registers tables)
    from app.models import AuthSession, Class, Enrollment, Event, Person, Tag
    from app.models import person_tags

    engine = create_engine(migrated)

    # legacy tables gone, event-schema tables present, alembic at head
    tables = set(inspect(engine).get_table_names())
    assert "person" in tables and "event" in tables
    assert "person_tags" in tables and "person_events" in tables
    assert not {"user", "teacher_profile", "student", "exam", "exam_subject",
                "exam_result", "student_event", "student_tag"} & tables
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0005"

    with sessionmaker(bind=engine)() as sess:
        # --- persons: 2 accounts + 2 students ----------------------------
        people = sess.query(Person).all()
        assert len(people) == 4

        teacher = next(p for p in people if p.payload["role"] == "teacher")
        assert teacher.payload == {"role": "teacher", "name": "陈老师",
                                   "subject": "math", "is_active": True}
        assert teacher.phone == "13800000001"       # login credentials as-is
        assert teacher.email == "chen@school.edu"
        assert teacher.password_hash == "hash-teacher"

        admin = next(p for p in people if p.payload["role"] == "admin")
        assert admin.payload == {"role": "admin", "name": "开发者", "is_active": True}
        assert admin.phone == "13800000000"
        assert "subject" not in admin.payload

        s1 = next(p for p in people if p.payload.get("admission_no") == "S2025001")
        assert s1.payload == {
            "role": "student", "name": "林晓雨", "admission_no": "S2025001",
            "gender": "F", "birth_date": "2012-05-12", "guardian_name": "林女士",
            "guardian_phone": "13900000001", "address": "解放路100号",
            "is_active": True,
        }
        s2 = next(p for p in people if p.payload.get("admission_no") == "S2025002")
        assert s2.payload["is_active"] is False          # status != "active"
        assert s2.payload["birth_date"] == "2012-11-03"  # ISO string
        assert s1.phone is None and s2.phone is None     # students don't log in
        assert len(s1.password_hash) == 32 and len(s2.password_hash) == 32  # uuid4().hex

        # --- class + enrollment (remapped FKs, dates as-is) ---------------
        cls = sess.query(Class).one()
        assert (cls.name, cls.grade_level, cls.academic_year) == ("七年级1班", 7, "2025/2026")
        assert cls.homeroom_person_id == teacher.id      # homeroom remap

        enrolls = sess.query(Enrollment).all()
        assert len(enrolls) == 2
        by_person = {e.person_id: e for e in enrolls}
        assert set(by_person) == {s1.id, s2.id}
        assert all(e.class_id == cls.id for e in enrolls)
        current = by_person[s1.id]
        assert (current.valid_from, current.valid_to, current.reason) == (
            date(2025, 9, 1), None, "admitted")
        closed = by_person[s2.id]
        assert (closed.valid_from, closed.valid_to, closed.reason) == (
            date(2025, 9, 1), date(2026, 6, 30), "graduated")

        # --- exam sitting event ------------------------------------------
        events = sess.query(Event).all()
        assert len(events) == 6  # 1 exam + 3 scores + 2 student_events
        exam_ev = next(e for e in events if e.type == "exam")
        assert exam_ev.title == "期中考试"
        assert exam_ev.start_time == datetime(2025, 11, 18, 9, 0)  # exam day 09:00
        assert exam_ev.payload == {"full_scores": {"math": 120.0, "english": 100.0}}
        assert {p.id for p in exam_ev.attendees} == {s1.id, s2.id}  # students w/ results

        # --- score events (one per exam_result) ---------------------------
        scores = [e for e in events if e.type == "score"]
        assert len(scores) == 3
        for sc in scores:
            assert sc.title == f"期中考试·{sc.payload['subject']}"  # "·" separator
            assert sc.start_time == datetime(2025, 11, 18, 9, 0)   # same date as sitting
        math_s1 = next(sc for sc in scores
                       if sc.payload["subject"] == "math" and sc.attendees[0].id == s1.id)
        assert math_s1.payload == {"subject": "math", "max_score": 120.0,
                                   "score": 95.0, "absent": False}
        english_s1 = next(sc for sc in scores
                          if sc.payload["subject"] == "english" and sc.attendees[0].id == s1.id)
        assert english_s1.payload == {"subject": "english", "max_score": 100.0,
                                      "score": 88.0, "absent": False}
        absent_sc = next(sc for sc in scores if sc.attendees[0].id == s2.id)
        assert absent_sc.payload == {"subject": "math", "max_score": 120.0,
                                     "absent": True}     # no "score" key when absent
        assert absent_sc.title == "期中考试·math"

        # --- student_event rows preserved 1:1 (free-form payload passthrough)
        visit = next(e for e in events if e.type == "home_visited")
        assert visit.title == "家访"
        assert visit.description == "跟进出勤"
        assert visit.payload == {"title": "家访", "summary": "频繁迟到",
                                 "description": "跟进出勤"}
        assert visit.start_time == datetime(2026, 3, 20, 19, 0)
        assert [p.id for p in visit.attendees] == [s1.id]
        birthday = next(e for e in events if e.type == "birthday")
        assert birthday.title == "生日"
        assert birthday.start_time == datetime(2025, 11, 3, 8, 0)  # past occurrence
        assert [p.id for p in birthday.attendees] == [s2.id]

        # --- tags + person_tags --------------------------------------------
        tags = sess.query(Tag).all()
        assert {t.name for t in tags} == {"需关注", "课代表"}
        focus = next(t for t in tags if t.name == "需关注")
        rows = sess.execute(select(person_tags.c.person_id, person_tags.c.tag_id)).all()
        assert rows == [(s1.id, focus.id)]

        # --- auth_session: token kept, remapped; unknown-user row dropped ---
        sessions = sess.query(AuthSession).all()
        assert len(sessions) == 1
        assert sessions[0].token == TOKEN
        assert sessions[0].person_id == teacher.id
    engine.dispose()


def test_downgrade_refuses(migrated):
    mod = _load_revision()
    with pytest.raises(NotImplementedError, match="lossy"):
        mod.downgrade()


def test_upgrade_is_noop_when_already_migrated(alembic_cfg, migrated):
    """Second run of the revision's upgrade(): legacy "user" is gone and
    "person" exists → early-return guard, data untouched, no exception."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    import app.models  # noqa: F401
    from app.models import Event, Person

    mod = _load_revision()
    engine = create_engine(migrated)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()
    with sessionmaker(bind=engine)() as sess:
        assert sess.query(Person).count() == 4
        assert sess.query(Event).count() == 6
    engine.dispose()
