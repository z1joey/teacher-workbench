"""Admin /admin/db/clear-business keeps admins, wipes demo/business rows."""
from __future__ import annotations

import pytest

import app.database as database_module
from app.models import AuthSession, Class, Event, Feedback, Person
from app.routers import admin as admin_router
from app.routers import auth, data as data_router
from app.seed import seed
from app.unassigned import UNASSIGNED_ACADEMIC_YEAR, UNASSIGNED_CLASS_NAME
from tests.conftest import seed_person, seed_token

ADMIN_TOKEN = "b" * 64
TEACHER_TOKEN = "c" * 64


@pytest.fixture()
def client(make_client, db, engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(engine.url))
    monkeypatch.setenv("ADMIN_EMAIL", "admin136@test.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-pass-123")
    monkeypatch.setattr(database_module, "engine", engine)
    tc = make_client(
        auth.router,
        admin_router.router,
        data_router.router,
        auth_dependency=False,
    )
    admin_p = seed_person(
        db,
        "admin136@test.example",
        phone="13600000000",
        role="admin",
        name="管理员",
    )
    teacher_p = seed_person(
        db,
        "teacher@test.example",
        phone="13800000001",
        role="teacher",
        name="演示教师",
    )
    seed_token(db, admin_p, ADMIN_TOKEN)
    seed_token(db, teacher_p, TEACHER_TOKEN)
    seed(db, teacher=teacher_p, include_admin=False)
    db.commit()
    tc.headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
    yield tc


def test_admin_clear_business_keeps_admin_and_wipes_demo(client, db):
    assert db.query(Person).filter(Person.payload["role"].as_string() == "student").count() >= 10
    assert db.query(Person).filter(Person.payload["role"].as_string() == "teacher").count() >= 1
    admin_id = db.query(Person).filter(Person.email == "admin136@test.example").one().id

    res = client.post("/api/admin/db/clear-business")
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True

    db.expire_all()
    assert db.get(Person, admin_id) is not None
    assert db.get(AuthSession, ADMIN_TOKEN) is not None
    assert db.query(Person).filter(Person.payload["role"].as_string() == "student").count() == 0
    assert db.query(Person).filter(Person.payload["role"].as_string() == "teacher").count() == 0
    assert db.query(Event).count() == 0
    assert (
        db.query(Class)
        .filter(Class.name == UNASSIGNED_CLASS_NAME, Class.academic_year == UNASSIGNED_ACADEMIC_YEAR)
        .count()
        == 1
    )


def test_admin_clear_business_requires_admin(client, db):
    res = client.post(
        "/api/admin/db/clear-business",
        headers={"Authorization": f"Bearer {TEACHER_TOKEN}"},
    )
    assert res.status_code == 403


def test_admin_clear_business_failure_is_atomic(client, db, monkeypatch):
    students_before = db.query(Person).filter(Person.payload["role"].as_string() == "student").count()

    def boom(*args, **kwargs):
        raise RuntimeError("simulated clear failure")

    monkeypatch.setattr(admin_router, "clear_business_data", boom)
    res = client.post("/api/admin/db/clear-business")
    assert res.status_code == 500
    assert "清空失败" in res.json()["detail"]

    db.expire_all()
    assert (
        db.query(Person).filter(Person.payload["role"].as_string() == "student").count()
        == students_before
    )


def test_admin_clear_business_removes_feedback(client, db):
    teacher = db.query(Person).filter(Person.email == "teacher@test.example").one()
    db.add(
        Feedback(
            person_id=teacher.id,
            feature="home",
            content="demo feedback",
        )
    )
    db.commit()
    assert db.query(Feedback).count() == 1

    res = client.post("/api/admin/db/clear-business")
    assert res.status_code == 200

    db.expire_all()
    assert db.query(Feedback).count() == 0
