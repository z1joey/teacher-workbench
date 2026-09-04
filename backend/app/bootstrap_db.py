"""Entrypoint schema bootstrap: create the event-schema tables.

Alembic 0005 (event schema) is the path for existing PostgreSQL databases;
fresh databases are created here via metadata.create_all (idempotent —
existing tables are left alone). Run `python -m app.seed` for a fresh
database with demo data.
"""
from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import Base, engine


def main() -> None:
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    main()
