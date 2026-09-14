"""按班级圈定考试参加者：class_ids 选中班级的在读学生进入 attendees
（学生时间线因此出现考试事件）；未选中班级的学生不出现；不选 = 全校。"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from app.models import Class, Event, Person
from app.routers import exams as exams_router
from tests.test_scores_events import (
    _enroll,
    _headers,
    _seed_class,
    _seed_person,
    _seed_teacher,
)


@pytest.fixture()
def ctx(make_client, db):
    teacher = _seed_teacher(db)
    headers = _headers(db, teacher)
    client = make_client(exams_router.router)

    a = _seed_class(db, "初一1班", "2025/2026")
    b = _seed_class(db, "初二2班", "2025/2026")
    in_a = _seed_person(db, "张一", "S1")
    in_b = _seed_person(db, "李二", "S2")
    free = _seed_person(db, "赵三", "S3")  # 未分班
    _enroll(db, in_a, a)
    _enroll(db, in_b, b)
    db.commit()

    def attendee_ids(student: Person) -> set[str]:
        exam = (
            db.query(Event)
            .filter(Event.type == "exam", Event.attendees.any(Person.id == student.id))
            .all()
        )
        return {e.title for e in exam}

    return {
        "client": client,
        "db": db,
        "headers": headers,
        "classes": {"a": a, "b": b},
        "students": {"in_a": in_a, "in_b": in_b, "free": free},
        "attendee_ids": attendee_ids,
    }


def _create(ctx, name, class_ids):
    return ctx["client"].post(
        "/api/exams",
        json={
            "name": name,
            "exam_date": "2026-09-09",
            "subjects": [{"subject": "语文", "full_score": 100}],
            **({"class_ids": class_ids} if class_ids is not None else {}),
        },
        headers=ctx["headers"],
    )


def test_create_exam_scoped_to_selected_classes(ctx, db):
    """选中两个班：两班学生都带上考试事件；未分班学生不带。"""
    r = _create(ctx, "联合月考", [str(ctx["classes"]["a"].id), str(ctx["classes"]["b"].id)])
    assert r.status_code == 201, r.text

    db.expire_all()
    for s in (ctx["students"]["in_a"], ctx["students"]["in_b"]):
        assert ctx["attendee_ids"](s) == {"联合月考"}
    assert ctx["attendee_ids"](ctx["students"]["free"]) == set()


def test_create_exam_without_classes_is_school_wide(ctx, db):
    """不选班级 = 全校在读学生（含未分班）都带上考试事件。"""
    r = _create(ctx, "全校统考", None)
    assert r.status_code == 201, r.text

    db.expire_all()
    for s in ctx["students"].values():
        assert ctx["attendee_ids"](s) == {"全校统考"}


def test_exam_averages_empty_exam(ctx):
    """GET /exams/{id}/averages must succeed before any scores are entered."""
    r = _create(ctx, "其中考试", None)
    assert r.status_code == 201, r.text
    exam_id = r.json()["id"]
    r2 = ctx["client"].get(f"/api/exams/{exam_id}/averages", headers=ctx["headers"])
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["school"] == []
    assert data["classes"] == []


def test_create_exam_rejects_unknown_class(ctx):
    r = _create(ctx, "幽灵考试", [str(uuid.uuid4())])
    assert r.status_code == 400
    assert r.json()["detail"] == "class not found"
