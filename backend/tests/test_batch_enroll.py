"""批量分配：POST /classes/{id}/enrollments 一次把多个学生调入一个班级。"""
import uuid

from app.models import Enrollment, Event, Person
from tests.conftest import seed_person, seed_token


def _setup_teacher(db, email):
    from app.workspace import ensure_workspace_id

    teacher = seed_person(db, email, name="王老师")
    ensure_workspace_id(teacher)
    db.commit()
    token = seed_token(db, teacher, uuid.uuid4().hex)
    return teacher, {"Authorization": f"Bearer {token}"}


def _create_student(client, headers, name):
    r = client.post("/api/students", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _create_class(client, headers, name):
    r = client.post(
        "/api/classes",
        json={"name": name, "academic_year": "2025/2026"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_batch_enroll_from_unassigned(client, db):
    _, headers = _setup_teacher(db, "batch-a@test.example")
    s1 = _create_student(client, headers, "学生一")
    s2 = _create_student(client, headers, "学生二")
    class_id = _create_class(client, headers, "七年级9班")

    r = client.post(
        f"/api/classes/{class_id}/enrollments",
        json={"student_ids": [s1["id"], s2["id"]]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [m["name"] for m in body["moved"]] == ["学生一", "学生二"]
    assert body["skipped"] == []

    sid = uuid.UUID(s1["id"])
    old = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == sid, Enrollment.reason == "admitted")
        .one()
    )
    assert old.valid_to is not None
    new = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == sid, Enrollment.valid_to.is_(None))
        .one()
    )
    assert str(new.class_id) == class_id
    event = (
        db.query(Event)
        .filter(Event.type == "class_moved", Event.attendees.any(Person.id == sid))
        .one()
    )
    assert event.title == "加入班级"
    assert event.payload.get("to_class") == "七年级9班"
    assert event.payload.get("from_class") is None


def test_batch_move_between_classes(client, db):
    _, headers = _setup_teacher(db, "batch-b@test.example")
    s = _create_student(client, headers, "转班生")
    class_a = _create_class(client, headers, "一班")
    class_b = _create_class(client, headers, "二班")
    r = client.patch(
        f"/api/students/{s['id']}", json={"class_id": class_a}, headers=headers
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/classes/{class_b}/enrollments",
        json={"student_ids": [s["id"]]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["moved"][0]["name"] == "转班生"

    sid = uuid.UUID(s["id"])
    closed = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == sid, Enrollment.reason == "moved")
        .all()
    )
    assert len(closed) == 2  # 一班 + 二班
    assert sum(1 for e in closed if e.valid_to is None) == 1
    event = (
        db.query(Event)
        .filter(
            Event.type == "class_moved",
            Event.title == "转班",
            Event.attendees.any(Person.id == sid),
        )
        .one()
    )
    assert event.payload == {"from_class": "一班", "to_class": "二班"}


def test_batch_skips_students_already_in_target(client, db):
    _, headers = _setup_teacher(db, "batch-c@test.example")
    s1 = _create_student(client, headers, "已在册")
    s2 = _create_student(client, headers, "待转入")
    class_id = _create_class(client, headers, "七年级8班")
    r = client.patch(
        f"/api/students/{s1['id']}", json={"class_id": class_id}, headers=headers
    )
    assert r.status_code == 200, r.text

    r = client.post(
        f"/api/classes/{class_id}/enrollments",
        json={"student_ids": [s1["id"], s2["id"]]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert [m["name"] for m in body["moved"]] == ["待转入"]
    assert body["skipped"] == ["已在册"]


def test_batch_empty_student_ids_rejected(client, db):
    _, headers = _setup_teacher(db, "batch-d@test.example")
    class_id = _create_class(client, headers, "七年级7班")
    r = client.post(
        f"/api/classes/{class_id}/enrollments",
        json={"student_ids": []},
        headers=headers,
    )
    assert r.status_code == 422


def test_batch_rejects_student_from_other_workspace(client, db):
    _, headers = _setup_teacher(db, "batch-e@test.example")
    class_id = _create_class(client, headers, "七年级6班")
    _, other_headers = _setup_teacher(db, "batch-e-other@test.example")
    outsider = _create_student(client, other_headers, "别人家的学生")

    r = client.post(
        f"/api/classes/{class_id}/enrollments",
        json={"student_ids": [outsider["id"]]},
        headers=headers,
    )
    assert r.status_code == 404


def test_batch_rejects_class_from_other_workspace(client, db):
    _, headers = _setup_teacher(db, "batch-f@test.example")
    s = _create_student(client, headers, "本校学生")
    _, other_headers = _setup_teacher(db, "batch-f-other@test.example")
    foreign_class = _create_class(client, other_headers, "别班")

    r = client.post(
        f"/api/classes/{foreign_class}/enrollments",
        json={"student_ids": [s["id"]]},
        headers=headers,
    )
    assert r.status_code == 404
