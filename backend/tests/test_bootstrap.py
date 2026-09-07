"""Locks the deploy-path behavior of app.bootstrap_db (the Docker CMD step):

- legacy volume (legacy `user` table, no `person`) → the real Alembic
  upgrade to head runs and create_all does NOT (upgrade is mocked here — the
  real chain is exercised end-to-end in tests/test_migrations_0005.py),
- fresh database → create_all + a REAL stamp: alembic_version must land at
  the chain head so the next migration never re-runs the chain,
- already-migrated database → a no-op that touches neither command.

Each test rebinds the module-level engine to a tmp SQLite file and points
DATABASE_URL at it (alembic/env.py prefers the env var) so real Alembic
commands can't leak onto the dev database — same discipline as
tests/test_migrations_0005.py.
"""
import alembic.command
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app import bootstrap_db


def _head(cfg) -> str:
    return ScriptDirectory.from_config(cfg).get_current_head()


def test_legacy_volume_runs_upgrade_not_create_all(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE "user" (id INTEGER PRIMARY KEY, name VARCHAR(50))'))
    monkeypatch.setattr(bootstrap_db, "engine", engine)

    calls = []
    monkeypatch.setattr(
        alembic.command, "upgrade", lambda cfg, rev: calls.append(("upgrade", rev))
    )
    bootstrap_db.main()

    assert calls == [("upgrade", "head")]
    # create_all must not have run: with the upgrade mocked, no new-schema
    # table may exist on this engine.
    assert not inspect(engine).has_table("person")
    engine.dispose()


def test_fresh_db_creates_tables_and_stamps_head(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)

    bootstrap_db.main()  # real stamp, against DATABASE_URL = the tmp file

    insp = inspect(engine)
    assert insp.has_table("person")
    assert insp.has_table("class")
    assert insp.has_table("event")
    assert insp.has_table("alembic_version")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _head(bootstrap_db._alembic_config())
    engine.dispose()


def test_already_migrated_db_is_noop(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)
    bootstrap_db.main()  # bring it to head for real, first

    calls = []
    monkeypatch.setattr(alembic.command, "upgrade", lambda cfg, rev: calls.append("upgrade"))
    monkeypatch.setattr(alembic.command, "stamp", lambda cfg, rev: calls.append("stamp"))
    bootstrap_db.main()

    assert calls == []
    engine.dispose()
