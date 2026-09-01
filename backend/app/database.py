import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# PostgreSQL in deployment (docker-compose sets DATABASE_URL); SQLite stands
# in for local runs outside Docker. The schema is PostgreSQL-first
# (see docs/design.md), so this really is just a connection-string change.
DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./teacher_workbench.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
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
