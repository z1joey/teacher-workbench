"""Locks the deploy-path behavior of app.bootstrap_db (the Docker CMD step):

- fresh database → alembic upgrade head creates the schema,
- already-migrated database → a second bootstrap is idempotent.

Each test rebinds the module-level engine to a tmp SQLite file and points
DATABASE_URL at it (alembic/env.py prefers the env var) so real Alembic
commands can't leak onto the dev database.
"""
from alembic.script import ScriptDirectory
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Table,
    create_engine,
    inspect,
    text,
)

import pytest

from app import bootstrap_db


def _head(cfg) -> str:
    return ScriptDirectory.from_config(cfg).get_current_head()


def test_fresh_db_runs_upgrade_creates_schema(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)

    bootstrap_db.main()

    insp = inspect(engine)
    assert insp.has_table("person")
    assert insp.has_table("class")
    assert insp.has_table("event")
    assert insp.has_table("alembic_version")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _head(bootstrap_db._alembic_config())
    engine.dispose()


def test_pre_release_revision_stamps_head(tmp_path, monkeypatch):
    """Volumes at old chain head (e.g. 0011) reconcile to squashed 0001."""
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)

    bootstrap_db.main()
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '0011'"))

    bootstrap_db.main()

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == _head(bootstrap_db._alembic_config())
    engine.dispose()


def test_legacy_student_era_schema_fails_fast(tmp_path, monkeypatch):
    """A pre-person volume (student/teacher era, no alembic_version) must be
    rejected with wipe guidance, not crash inside create_all on an
    incompatible FK — the production crash of 2026-09-14."""
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)
    legacy = MetaData()
    Table("class", legacy, Column("id", Integer, primary_key=True))
    Table("student", legacy, Column("id", Integer, primary_key=True))
    legacy.create_all(engine)

    with pytest.raises(SystemExit, match="docker compose down -v"):
        bootstrap_db.main()

    # The rejection must happen before any migration touches the volume.
    insp = inspect(engine)
    assert insp.has_table("class")
    assert not insp.has_table("person")
    assert not insp.has_table("alembic_version")
    engine.dispose()


def test_already_migrated_db_is_idempotent(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'boot.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(bootstrap_db, "engine", engine)
    bootstrap_db.main()

    with engine.connect() as conn:
        version_before = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()

    bootstrap_db.main()

    with engine.connect() as conn:
        version_after = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar()
    assert version_before == version_after == _head(bootstrap_db._alembic_config())
    engine.dispose()
