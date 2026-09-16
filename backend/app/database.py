import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def resolve_database_url() -> str:
    """Return the SQLAlchemy database URL.

    Prefer an explicit ``DATABASE_URL``. In Docker/production, build from
    ``POSTGRES_*`` with proper URL-encoding so passwords containing ``@``,
    ``:``, ``/``, etc. do not corrupt the connection string when interpolated
    raw in docker-compose.
    """
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit

    user = os.environ.get("POSTGRES_USER", "").strip()
    password = os.environ.get("POSTGRES_PASSWORD", "")
    dbname = os.environ.get("POSTGRES_DB", "").strip()
    host = (os.environ.get("POSTGRES_HOST", "db").strip() or "db")
    port = (os.environ.get("POSTGRES_PORT", "5432").strip() or "5432")

    if user and password and dbname:
        return (
            f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
            f"@{host}:{port}/{quote_plus(dbname)}"
        )

    raise RuntimeError(
        "DATABASE_URL is required (or set POSTGRES_USER, POSTGRES_PASSWORD, "
        "and POSTGRES_DB). Copy .env.example to .env and run "
        "./scripts/run-dev.sh (or export DATABASE_URL before starting the backend)."
    )


# PostgreSQL everywhere outside unit tests (tests set DATABASE_URL to SQLite).
DATABASE_URL: str = resolve_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
