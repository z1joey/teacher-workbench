import uuid

from app.models import Class, Enrollment
from app.routers import students
from app.unassigned import (
    UNASSIGNED_ACADEMIC_YEAR,
    UNASSIGNED_CLASS_NAME,
    class_for_api,
    ensure_unassigned_class,
    is_unassigned_class,
)
from tests.conftest import seed_person, seed_token


def test_ensure_unassigned_class_is_idempotent(db):
    first = ensure_unassigned_class(db)
    second = ensure_unassigned_class(db)
    assert first.id == second.id
    assert first.name == UNASSIGNED_CLASS_NAME
    assert first.academic_year == UNASSIGNED_ACADEMIC_YEAR
    db.commit()
    assert db.query(Class).count() == 1


def test_class_for_api_hides_unassigned(db):
    cls = ensure_unassigned_class(db)
    assert class_for_api(cls) is None


def test_create_student_without_class_enrolls_in_unassigned(client, db):
    from app.workspace import ensure_workspace_id

    teacher = seed_person(db, "wang-unassigned@test.example", phone="13800000081", name="王老师")
    ensure_workspace_id(teacher)
    token = seed_token(db, teacher, uuid.uuid4().hex)
    headers = {"Authorization": f"Bearer {token}"}
    unassigned = ensure_unassigned_class(db)
    db.commit()

    r = client.post("/api/students", json={"name": "待分班"}, headers=headers)
    assert r.status_code == 201, r.text
    listed = client.get("/api/students", headers=headers).json()
    row = next(item for item in listed if item["id"] == r.json()["id"])
    assert row["class"] is None
    enrollment = db.query(Enrollment).filter(
        Enrollment.person_id == uuid.UUID(r.json()["id"]),
        Enrollment.valid_to.is_(None),
    ).one()
    assert enrollment.class_id == unassigned.id
    assert is_unassigned_class(db.get(Class, enrollment.class_id))

    listed = client.get("/api/classes", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    pool = next(row for row in rows if row.get("is_unassigned"))
    assert pool["id"] == str(unassigned.id)
    assert pool["name"] == UNASSIGNED_CLASS_NAME
    assert pool["student_count"] == 1

    detail = client.get(f"/api/classes/{unassigned.id}", headers=headers).json()
    assert detail["class"]["is_unassigned"] is True
    assert [s["name"] for s in detail["students"]] == ["待分班"]
