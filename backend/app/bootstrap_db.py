"""Entrypoint schema bootstrap for deploy and local dev.

Runs Alembic to head, then lightweight data fixes (unassigned class,
workspace backfill, projected birthdays). Demo data: python -m app.seed

Pre-release volumes that still record an old revision id (e.g. 0011) are
reconciled by stamping the squashed head when the event schema is present.
Any legacy pre-``person`` schema (the ``user`` era, the older
``student``/``teacher`` era) must be wiped first.
"""
from pathlib import Path

import alembic.command
import alembic.config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .create_admin import bootstrap_admin_from_env
from .database import Base, engine
from .eventing import sync_all_birthday_events
from .unassigned import ensure_unassigned_class
from .workspace import migrate_legacy_workspace

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> alembic.config.Config:
    cfg = alembic.config.Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _revision_in_script(cfg: alembic.config.Config, revision_id: str | None) -> bool:
    if not revision_id:
        return False
    try:
        ScriptDirectory.from_config(cfg).get_revision(revision_id)
    except CommandError:
        return False
    return True


def _reconcile_squashed_migration(cfg: alembic.config.Config) -> None:
    """Stamp squashed head when a pre-release volume still records 0002–0011."""
    insp = inspect(engine)
    # Any non-empty volume without the person table predates the squashed
    # chain; create_all would half-run against it and die on the first
    # UUID-vs-integer FK (the 2026-09-14 production crash-loop). Reject it
    # before alembic touches the schema. Covers both the user-table era and
    # the older student/teacher era.
    if insp.get_table_names() and not insp.has_table("person"):
        raise SystemExit(
            "legacy pre-person schema detected (no person table). "
            "Wipe the database volume before deploying: docker compose down -v"
        )
    if not insp.has_table("alembic_version"):
        return
    with engine.connect() as conn:
        current = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    if _revision_in_script(cfg, current):
        return
    if insp.has_table("person"):
        head = ScriptDirectory.from_config(cfg).get_current_head()
        print(f"reconciling squashed migration: {current} -> {head}")
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE alembic_version SET version_num = :head"),
                {"head": head},
            )
        return
    raise SystemExit(
        f"unknown alembic revision {current!r} with no event schema. "
        "Wipe the database volume: docker compose down -v"
    )


def ensure_schema() -> None:
    """Idempotent setup used on app startup and in Docker CMD."""
    cfg = _alembic_config()
    _reconcile_squashed_migration(cfg)
    alembic.command.upgrade(cfg, "head")
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        ensure_unassigned_class(db)
        migrate_legacy_workspace(db)
        sync_all_birthday_events(db)
        bootstrap_admin_from_env(db)
        db.commit()


def _drop_all_database_tables() -> None:
    """Drop every user table in the catalog, including legacy tables no longer
    registered on ``Base.metadata`` (pre-person ``teacher``/``student`` era).

    ``Base.metadata.drop_all`` alone leaves those orphans behind, which makes
    ``ensure_schema`` think the volume is a broken legacy schema and abort.
    """
    insp = inspect(engine)
    tables = insp.get_table_names()
    if not tables:
        return
    cascade = " CASCADE" if engine.dialect.name == "postgresql" else ""
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = OFF"))
        for name in tables:
            conn.execute(text(f'DROP TABLE IF EXISTS "{name}"{cascade}'))
        if engine.dialect.name == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = ON"))


def wipe_and_rebootstrap() -> None:
    """Drop every table and rerun the same bootstrap path as app startup.

    Call only after any request-scoped ORM sessions are closed — DDL while
    auth still holds a read transaction deadlocks on PostgreSQL (see
    routers/data._clear_business_data).

    If bootstrap fails after a successful drop, ``ensure_schema`` is retried
    once before re-raising so the volume is less likely to stay headless.
    """
    engine.dispose()
    try:
        _drop_all_database_tables()
        ensure_schema()
    except Exception as exc:
        try:
            ensure_schema()
        except Exception:
            raise exc


def main() -> None:
    ensure_schema()


if __name__ == "__main__":
    main()
