"""Entrypoint schema bootstrap for deploy and local dev.

Runs Alembic to head, then lightweight data fixes (unassigned class,
workspace backfill, projected birthdays). Demo data: python -m app.seed

v1 note: pre-release databases must be wiped (docker compose down -v) before
the first deploy on this chain — alembic_version from the old 0001–0011
history is not compatible.
"""
from pathlib import Path

import alembic.command
import alembic.config
from sqlalchemy.orm import Session

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import engine
from .eventing import sync_all_birthday_events
from .unassigned import ensure_unassigned_class
from .workspace import migrate_legacy_workspace

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> alembic.config.Config:
    cfg = alembic.config.Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def ensure_schema() -> None:
    """Idempotent setup used on app startup and in Docker CMD."""
    alembic.command.upgrade(_alembic_config(), "head")
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        ensure_unassigned_class(db)
        migrate_legacy_workspace(db)
        sync_all_birthday_events(db)
        db.commit()


def main() -> None:
    ensure_schema()


if __name__ == "__main__":
    main()
