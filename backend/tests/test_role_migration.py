"""Runs the real alembic chain on a throwaway SQLite database:
upgrade to 0001 (legacy schema), insert legacy rows, upgrade to head —
then asserts the user/role migration preserved IDs, roles and sessions.
This mirrors the production path (existing pgdata volume with legacy tables)."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def migrated_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "0001")  # legacy schema

    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO teacher (id, name, phone, email, password_hash, subject, is_active, is_admin, created_at) VALUES"
            " (1, '开发者', '13800000000', 'admin@school.dev', 'x', NULL, 1, 1, '2026-01-01 00:00:00'),"
            " (2, '陈老师', '13800000001', 'chen@school.edu', 'x', 'math', 1, 0, '2026-01-01 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO auth_session (token, teacher_id, created_at) VALUES ('tok123', 2, '2026-01-02 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO student (id, admission_no, name, status, created_at, updated_at)"
            " VALUES (1, 'S1', '林晓雨', 'active', '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO class (id, name, grade_level, academic_year, homeroom_teacher_id)"
            " VALUES (1, '七年级1班', 7, '2025/2026', 2)"
        ))
        conn.execute(text("INSERT INTO exam (id, name, exam_date) VALUES (1, '期中考试', '2026-04-15')"))
        conn.execute(text(
            "INSERT INTO exam_subject (id, exam_id, subject, full_score) VALUES (1, 1, 'math', 100.0)"
        ))
        conn.execute(text(
            "INSERT INTO exam_result (id, student_id, exam_subject_id, score, status, entered_by, created_at, updated_at)"
            " VALUES (1, 1, 1, 88.0, 'entered', 2, '2026-01-01 00:00:00', '2026-01-01 00:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO student_event (id, student_id, event_type, occurred_at, actor_teacher_id, payload)"
            " VALUES (1, 1, 'enrolled', '2026-01-01 00:00:00', 2, '{}')"
        ))
        conn.execute(text(
            "INSERT INTO home_visit (id, student_id, teacher_id, visited_at, summary, follow_up_needed)"
            " VALUES (1, 1, 2, '2026-01-01 00:00:00', 'legacy visit', 0)"
        ))
    eng.dispose()

    command.upgrade(cfg, "head")
    return create_engine(url)


def test_users_migrated_with_roles_and_preserved_ids(migrated_db):
    rows = inspect(migrated_db)
    assert "user" in rows.get_table_names()
    assert "teacher" not in rows.get_table_names()
    assert "home_visit" not in rows.get_table_names()
    assert "teacher_profile" in rows.get_table_names()

    with migrated_db.connect() as conn:
        users = conn.execute(text('SELECT id, name, role, is_active FROM "user" ORDER BY id')).all()
        assert users == [(1, "开发者", "admin", True), (2, "陈老师", "teacher", True)]
        subjects = conn.execute(text("SELECT user_id, subject FROM teacher_profile")).all()
        assert subjects == [(2, "math")]
        sessions = conn.execute(text("SELECT token, user_id FROM auth_session")).all()
        assert sessions == [("tok123", 2)]
        assert conn.execute(text("SELECT homeroom_teacher_id FROM class WHERE id=1")).scalar() == 2
        assert conn.execute(text("SELECT entered_by FROM exam_result WHERE id=1")).scalar() == 2
        assert conn.execute(text("SELECT actor_teacher_id FROM student_event WHERE id=1")).scalar() == 2


def test_user_phone_unique_constraint_survives(migrated_db):
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        with migrated_db.begin() as conn:
            conn.execute(text(
                'INSERT INTO "user" (name, phone, password_hash, role, is_active, created_at)'
                " VALUES ('重复', '13800000001', 'x', 'teacher', 1, '2026-01-01 00:00:00')"
            ))
