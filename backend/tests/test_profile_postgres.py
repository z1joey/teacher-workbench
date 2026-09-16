"""PostgreSQL-only: GET /profile after demo seed.

Default pytest uses SQLite, which accepts ``SELECT DISTINCT person.*
ORDER BY payload->>'admission_no'``. Production PostgreSQL raises
``for SELECT DISTINCT, ORDER BY expressions must appear in select list``
once demo seed creates archived 六1班. Run with:

    RUN_POSTGRES_TESTS=1 DATABASE_URL=postgresql+psycopg://... pytest tests/test_profile_postgres.py
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_TESTS") != "1",
    reason="set RUN_POSTGRES_TESTS=1 with a PostgreSQL DATABASE_URL",
)


def _pg_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("DATABASE_URL is not PostgreSQL")
    return url


@pytest.fixture()
def pg_client():
    url = _pg_url()
    from app.database import get_db
    from app.main import app as fastapi_app
    from app.unassigned import ensure_unassigned_class

    engine = create_engine(url)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        ensure_unassigned_class(session)
        session.commit()
    finally:
        session.close()

    def _override():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = _override
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()
    engine.dispose()


def test_profile_after_demo_seed_on_postgres(pg_client):
    email = f"pg-profile-{uuid.uuid4().hex[:12]}@test.example"
    reg = pg_client.post(
        "/api/auth/register",
        json={"email": email, "password": "123456", "name": "新老师"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    before = pg_client.get("/api/profile", headers=headers)
    assert before.status_code == 200, before.text

    seeded = pg_client.post("/api/data/demo/seed", headers=headers)
    assert seeded.status_code == 200, seeded.text

    after = pg_client.get("/api/profile", headers=headers)
    assert after.status_code == 200, after.text
    body = after.json()
    assert len(body["classes"]) >= 2
    assert body["stats"]["interactions"] > 0
    archived = [c for c in body["archived_classes"] if c["name"] == "六1班"]
    assert archived and len(archived[0]["students"]) == 6
    assert len(body["graduated_students"]) == 6
