"""Admin /admin/db/reset must not deadlock or leave alembic/bootstrap broken."""
from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import app.database as database_module
from app import bootstrap_db
from app.models import AuthSession, Class, Person
from app.routers import admin as admin_router
from app.routers import auth
from app.unassigned import UNASSIGNED_ACADEMIC_YEAR, UNASSIGNED_CLASS_NAME
from tests.conftest import seed_person, seed_token

ADMIN_TOKEN = "a" * 64


@pytest.fixture()
def client(make_client, db, engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("ADMIN_EMAIL", "admin136@test.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(bootstrap_db, "engine", engine)
    tc = make_client(auth.router, admin_router.router, auth_dependency=False)
    admin_p = seed_person(
        db,
        "admin136@test.example",
        phone="13600000000",
        role="admin",
        name="管理员",
    )
    seed_person(db, "extra@test.example", role="teacher", name="多余")
    seed_token(db, admin_p, ADMIN_TOKEN)
    db.commit()
    tc.headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    yield tc


def test_admin_db_reset_wipes_and_rebootstraps(client, db):
    assert db.query(Person).count() >= 2

    res = client.post("/api/admin/db/reset")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["relogin_required"] is True

    db.expire_all()
    insp = inspect(db.get_bind())
    assert insp.has_table("alembic_version")
    version = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    head = ScriptDirectory.from_config(bootstrap_db._alembic_config()).get_current_head()
    assert version == head

    assert db.query(Person).count() == 1
    unassigned = (
        db.query(Class)
        .filter(
            Class.name == UNASSIGNED_CLASS_NAME,
            Class.academic_year == UNASSIGNED_ACADEMIC_YEAR,
        )
        .first()
    )
    assert unassigned is not None

    # Old bearer token is invalid after reset — must not cascade 500s.
    stale = client.post("/api/admin/db/reset")
    assert stale.status_code == 401
    assert db.get(AuthSession, ADMIN_TOKEN) is None


def test_wipe_and_rebootstrap_repairs_after_bootstrap_failure(engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("ADMIN_EMAIL", "admin136@test.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(bootstrap_db, "engine", engine)

    calls = {"n": 0}
    real_ensure = bootstrap_db.ensure_schema

    def flaky_ensure():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated bootstrap failure")
        return real_ensure()

    monkeypatch.setattr(bootstrap_db, "ensure_schema", flaky_ensure)
    bootstrap_db.wipe_and_rebootstrap()

    insp = inspect(engine)
    assert insp.has_table("alembic_version")
    assert insp.has_table("person")


def test_admin_db_reset_failure_leaves_health_ok(client, db, monkeypatch):
    def boom():
        raise RuntimeError("simulated wipe failure")

    monkeypatch.setattr(admin_router, "wipe_and_rebootstrap", boom)
    res = client.post("/api/admin/db/reset")
    assert res.status_code == 500
    assert "重置失败" in res.json()["detail"]

    # Schema untouched — other admin endpoints still respond (not 500).
    stats = client.get("/api/admin/stats")
    assert stats.status_code == 200
    assert db.query(Person).count() >= 2
