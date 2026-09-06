"""Entrypoint schema bootstrap: bring any volume to the event schema.

- Existing legacy volume (legacy `user` table present, no `person`): run the
  real Alembic chain to head — 0005 migrates the legacy data in place.
- Otherwise: create the event-schema tables via metadata.create_all
  (idempotent — existing tables are left alone). On a fresh database with no
  `alembic_version` table yet, stamp head so the NEXT migration starts from
  head instead of re-running the chain on existing tables.

Run `python -m app.seed` for a fresh database with demo data.
"""
from pathlib import Path

import alembic.command
import alembic.config
from sqlalchemy import inspect

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import Base, engine

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> alembic.config.Config:
    # alembic/env.py prefers DATABASE_URL, so this targets the same database
    # the engine above talks to.
    cfg = alembic.config.Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def main() -> None:
    cfg = _alembic_config()
    insp = inspect(engine)
    if insp.has_table("user") and not insp.has_table("person"):
        # Legacy volume: 0005 migrates the legacy data to the event schema.
        print("legacy schema detected — running alembic upgrade head")
        alembic.command.upgrade(cfg, "head")
        return
    Base.metadata.create_all(engine)
    # re-inspect: the check must see what create_all just did
    if not inspect(engine).has_table("alembic_version"):
        # Fresh database: mark the chain as applied so future migrations
        # start from head instead of re-running on existing tables.
        print("fresh database — stamping alembic head")
        alembic.command.stamp(cfg, "head")


if __name__ == "__main__":
    main()
