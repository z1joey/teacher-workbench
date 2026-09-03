"""Alembic smoke test: the migration chain applies to a fresh database and
reverses cleanly. Uses a temp SQLite file; DATABASE_URL must not leak in."""
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def alembic_cfg(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'mig.db'}")
    return cfg


def test_upgrade_head_then_downgrade_base(alembic_cfg):
    from alembic import command

    url = alembic_cfg.get_main_option("sqlalchemy.url")
    command.upgrade(alembic_cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"student", "class", "enrollment", "exam", "exam_subject",
            "exam_result", "student_event", "auth_session"} <= tables

    command.downgrade(alembic_cfg, "base")
    tables_after = set(inspect(create_engine(url)).get_table_names())
    assert not tables_after - {"alembic_version"}
