"""Shared fixtures for the identity-swap test files (Person + payload).

`import app.main` still fails — students/classes/exams/dashboard routers
import the legacy schema until Tasks 5-6 migrate them — so tests cannot use
the real FastAPI app yet. Instead, each test builds a per-router app via
`make_client`, bound to the same tmp-file SQLite engine as the `db` fixture.
The full-app `client` fixture lands in Task 8 once all routers are migrated.
"""
import sys
import warnings
from pathlib import Path

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


@pytest.fixture()
def engine(tmp_path):
    """Per-test tmp-file SQLite engine with the new-package schema loaded."""
    eng = create_engine(
        f"sqlite:///{tmp_path}/tw.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Session on the same per-test engine that make_client binds apps to."""
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture()
def make_client(engine):
    """Factory building a fresh FastAPI app per call: get_db overridden onto
    the test engine, each router mounted at /api with the router-level auth
    dependency (mirroring app/main.py's include pattern)."""

    def _make(*routers, auth_dependency: bool = True) -> TestClient:
        application = FastAPI()
        TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        def _override():
            s = TestSession()
            try:
                yield s
            finally:
                s.close()

        application.dependency_overrides[get_db] = _override
        for router in routers:
            application.include_router(
                router,
                prefix="/api",
                dependencies=[Depends(get_current_person)] if auth_dependency else [],
            )
        return TestClient(application)

    return _make
