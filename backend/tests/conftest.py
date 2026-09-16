"""Shared fixtures + seeding helpers for the event-schema test suite.

Two ways to get an HTTP client, both bound to the same per-test tmp-file
SQLite engine as the `db` fixture:

- `make_client(*routers, auth_dependency=True)` builds a fresh FastAPI app
  per call with just the routers under test mounted at /api — fast and
  precise, used by the per-router behavior tests.
- `client` is the real `app.main` app with `get_db` overridden onto the test
  engine — for tests that need the full route table (404-on-removed-route
  guards, cross-router flows). It exists for future tests; nothing in the
  current suite depends on it beyond the smoke test and the route-removal
  guards in test_kp_qr_removal.py.

`seed_person` / `seed_token` are plain helper functions (import from
`tests.conftest`) so tests keep a linear arrange section instead of juggling
fixture return values.
"""
import os
import sys
import warnings
from pathlib import Path

# app.database requires DATABASE_URL at import; tests use their own SQLite engines.
os.environ.setdefault("DATABASE_URL", "sqlite://")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# fastapi.testclient re-exports starlette's, which deprecation-warns on
# import (httpx vs httpx2) — environmental noise, not our code.
warnings.filterwarnings(
    "ignore", category=Warning, message=r".*httpx.*starlette\.testclient.*"
)

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers the new tables on Base.metadata)
from app.database import Base, get_db
from app.deps import get_current_person
from app.payloads import validate_person_payload
from app.security import hash_password
from app.unassigned import ensure_unassigned_class


@pytest.fixture()
def engine(tmp_path):
    """Per-test tmp-file SQLite engine with the new-package schema loaded."""
    eng = create_engine(
        f"sqlite:///{tmp_path}/tw.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)()
    try:
        ensure_unassigned_class(session)
        session.commit()
    finally:
        session.close()
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Session on the same per-test engine that make_client/client bind to."""
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


def _make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _db_override(factory):
    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    return _override


@pytest.fixture()
def make_client(engine):
    """Factory building a fresh FastAPI app per call: get_db overridden onto
    the test engine, each router mounted at /api with the router-level auth
    dependency (mirroring app/main.py's include pattern)."""

    def _make(*routers, auth_dependency: bool = True) -> TestClient:
        application = FastAPI()
        application.dependency_overrides[get_db] = _db_override(
            _make_session_factory(engine)
        )
        for router in routers:
            application.include_router(
                router,
                prefix="/api",
                dependencies=[Depends(get_current_person)] if auth_dependency else [],
            )
        return TestClient(application)

    return _make


@pytest.fixture()
def client(engine):
    """The real full app (app.main) with get_db overridden onto the per-test
    engine. Mounts every router exactly like production — including the ones
    make_client leaves out — so removed routes really 404 and cross-router
    behavior is exercised. Note that app.main keeps the real auth dependency
    chain: seed credentials with `seed_person` + `seed_token` in `db`."""
    from app.database import get_db as app_get_db
    from app.main import app as fastapi_app

    fastapi_app.dependency_overrides[app_get_db] = _db_override(
        _make_session_factory(engine)
    )
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def seed_person(db, email: str | None, *, phone: str | None = None,
                role: str = "teacher",
                name: str = "用户", admission_no: str | None = None):
    """Insert a Person row with a registry-validated payload (the common
    arrange step of the router tests). `name` is a typed person column; the
    payload holds only role-specific attributes."""
    from app.models import Person

    data = {}
    if admission_no is not None:
        data["admission_no"] = admission_no
    payload = validate_person_payload(role, data)
    p = Person(name=name, email=email, phone=phone,
               password_hash=hash_password("123456"), payload=payload)
    db.add(p)
    db.flush()
    return p


def seed_token(db, person, token: str) -> str:
    """Mint a bearer-token AuthSession for `person` (committed)."""
    from app.models import AuthSession

    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return token
