"""Entrypoint schema bootstrap: bring any volume to the event schema.

- Existing legacy volume (legacy `user` table present, no `person`): run the
  real Alembic chain to head — 0005 migrates the legacy data in place.
- Otherwise: create the event-schema tables via metadata.create_all
  (idempotent — existing tables are left alone), then drop any DB-level
  event-type CHECK constraint left from older builds (types are validated in
  Python instead). On a fresh database with no `alembic_version` table yet,
  stamp head.

Run `python -m app.seed` for a fresh database with demo data.
"""
from pathlib import Path

import alembic.command
import alembic.config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import Base, engine
from .models import Event
from .payloads import validate_event_payload
from .eventing import sync_all_birthday_events
from .unassigned import ensure_unassigned_class
from .workspace import migrate_legacy_workspace

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> alembic.config.Config:
    cfg = alembic.config.Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _drop_event_type_check() -> None:
    """Remove ck_event_type_valid so new event types work without migrations."""
    if not inspect(engine).has_table("event"):
        return
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            conn.execute(text("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid"))
            return
        if dialect != "sqlite":
            return
        ddl = conn.execute(
            text("SELECT sql FROM sqlite_master WHERE type='table' AND name='event'")
        ).scalar()
        if not ddl or "ck_event_type_valid" not in ddl:
            return
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for stmt in (
            """
            CREATE TABLE event__new (
                id CHAR(32) NOT NULL PRIMARY KEY,
                type VARCHAR(40) NOT NULL,
                title VARCHAR(100) NOT NULL,
                description TEXT,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                location VARCHAR(200),
                payload JSON,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """,
            "INSERT INTO event__new SELECT * FROM event",
            "DROP TABLE event",
            "ALTER TABLE event__new RENAME TO event",
            "CREATE INDEX IF NOT EXISTS ix_event_type_time ON event (type, start_time)",
        ):
            conn.execute(text(stmt))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def _strip_class_legacy_columns() -> None:
    """Drop grade_level / homeroom_person_id from older class tables."""
    insp = inspect(engine)
    if not insp.has_table("class"):
        return
    cols = {c["name"] for c in insp.get_columns("class")}
    if "grade_level" not in cols and "homeroom_person_id" not in cols:
        return
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            conn.execute(text(
                "ALTER TABLE class DROP CONSTRAINT IF EXISTS class_homeroom_person_id_fkey"
            ))
            if "homeroom_person_id" in cols:
                conn.execute(text("ALTER TABLE class DROP COLUMN homeroom_person_id"))
            if "grade_level" in cols:
                conn.execute(text("ALTER TABLE class DROP COLUMN grade_level"))
            return
        if dialect != "sqlite":
            return
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for stmt in (
            """
            CREATE TABLE class__new (
                id CHAR(32) NOT NULL PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                academic_year VARCHAR(20) NOT NULL,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE (name, academic_year)
            )
            """,
            """
            INSERT INTO class__new (id, name, academic_year, created_at, updated_at)
            SELECT id, name, academic_year, created_at, updated_at FROM class
            """,
            "DROP TABLE class",
            "ALTER TABLE class__new RENAME TO class",
        ):
            conn.execute(text(stmt))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def _strip_follow_up_from_events() -> None:
    """Remove legacy follow_up notes from home-visit event payloads."""
    if not inspect(engine).has_table("event"):
        return
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        changed = False
        for ev in db.query(Event).filter(Event.type == "home_visited").all():
            payload = dict(ev.payload or {})
            if "follow_up" not in payload:
                continue
            payload.pop("follow_up", None)
            ev.payload = validate_event_payload("home_visited", payload)
            changed = True
        if changed:
            db.commit()


def _ensure_class_teacher_id() -> None:
    insp = inspect(engine)
    if not insp.has_table("class"):
        return
    cols = {c["name"] for c in insp.get_columns("class")}
    if "teacher_id" in cols:
        return
    with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            conn.execute(text(
                "ALTER TABLE class ADD COLUMN teacher_id UUID REFERENCES person(id)"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_class_teacher_id ON class (teacher_id)"
            ))
            return
        if dialect != "sqlite":
            return
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        for stmt in (
            """
            CREATE TABLE class__new (
                id CHAR(32) NOT NULL PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                academic_year VARCHAR(20) NOT NULL,
                teacher_id CHAR(32) REFERENCES person(id),
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                UNIQUE (name, academic_year)
            )
            """,
            """
            INSERT INTO class__new (id, name, academic_year, created_at, updated_at)
            SELECT id, name, academic_year, created_at, updated_at FROM class
            """,
            "DROP TABLE class",
            "ALTER TABLE class__new RENAME TO class",
            "CREATE INDEX IF NOT EXISTS ix_class_teacher_id ON class (teacher_id)",
        ):
            conn.execute(text(stmt))
        conn.execute(text("PRAGMA foreign_keys=ON"))


def _ensure_class_archived() -> None:
    """毕业功能：旧库的 class 表补 archived 列（纯加列，两方言都支持）。"""
    insp = inspect(engine)
    if not insp.has_table("class"):
        return
    cols = {c["name"] for c in insp.get_columns("class")}
    if "archived" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE class ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"
        ))


def ensure_schema() -> None:
    """Idempotent setup used on app startup and in Docker CMD."""
    Base.metadata.create_all(engine)
    _drop_event_type_check()
    _strip_class_legacy_columns()
    _ensure_class_teacher_id()
    _ensure_class_archived()
    _strip_follow_up_from_events()
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        ensure_unassigned_class(db)
        migrate_legacy_workspace(db)
        sync_all_birthday_events(db)
        db.commit()
    if not inspect(engine).has_table("alembic_version"):
        alembic.command.stamp(_alembic_config(), "head")


def main() -> None:
    cfg = _alembic_config()
    insp = inspect(engine)
    if insp.has_table("user") and not insp.has_table("person"):
        print("legacy schema detected — running alembic upgrade head")
        alembic.command.upgrade(cfg, "head")
        _drop_event_type_check()
        return
    ensure_schema()


if __name__ == "__main__":
    main()
