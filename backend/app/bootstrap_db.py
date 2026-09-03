"""Entrypoint schema bootstrap: bring any database to alembic head.

- Fresh database            -> upgrade head
- Legacy create_all volume  -> stamp 0001 (legacy baseline), then upgrade head
                              (runs 0002, which migrates teacher -> user)
- Already migrated          -> upgrade head (no-op)
"""
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def main() -> None:
    url = os.environ.get("DATABASE_URL", "sqlite:///./teacher_workbench.db")
    cfg = Config("alembic.ini")
    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    if "user" not in tables and "teacher" in tables:
        # Pre-Alembic database: mark it at the legacy baseline, then migrate.
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    main()
