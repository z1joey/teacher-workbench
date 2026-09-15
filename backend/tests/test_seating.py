"""班级座位表：行列自定义、座位→学生映射的保存/读取，以及
学生归属、一人一座、位置范围三道校验。"""
from __future__ import annotations

from datetime import date

import pytest

from app.models import Class, Enrollment, Event
from app.routers import classes as classes_router
from tests.conftest import seed_person, seed_token

TEACHER_TOKEN = "g" * 64
AUTH = {"Authorization": f"Bearer {TEACHER_TOKEN}"}


@pytest.fixture()
def client(make_client, db):
    tc = make_client(classes_router.router)
    teacher = seed_person(db, "chen@test.example", phone="13800000001", name="陈老师")
    seed_token(db, teacher, TEACHER_TOKEN)
    klass = Class(name="初一1班", academic_year="2025-09", teacher_id=teacher.id)
    db.add(klass)
    db.flush()
    s1 = seed_person(db, None, role="student", name="吴梓涵", admission_no="2025070701")
    s2 = seed_person(db, None, role="student", name="邢宇辰", admission_no="2025070702")
    outsider = seed_person(db, None, role="student", name="隔壁班", admission_no="S900")
    for s in (s1, s2):
        db.add(Enrollment(person_id=s.id, class_id=klass.id, valid_from=date(2025, 9, 1)))
    db.commit()
    return {
        "client": tc,
        "db": db,
        "class": klass,
        "students": {"s1": s1, "s2": s2, "outsider": outsider},
    }


def _get(ctx, klass):
    return ctx["client"].get(f"/api/classes/{klass.id}/seating", headers=AUTH)


def _put(ctx, klass, rows, cols, seats):
    return ctx["client"].put(
        f"/api/classes/{klass.id}/seating",
        json={"rows": rows, "cols": cols, "seats": seats},
        headers=AUTH,
    )


def test_seating_roundtrip(client):
    klass = client["class"]
    s1, s2 = client["students"]["s1"], client["students"]["s2"]

    r = _get(client, klass)
    assert r.status_code == 200
    assert r.json() == {"rows": 0, "cols": 0, "seats": {}}

    r = _put(client, klass, 2, 3, {"0": str(s1.id), "5": str(s2.id)})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "rows": 2,
        "cols": 3,
        "seats": {"0": str(s1.id), "5": str(s2.id)},
    }

    r = _get(client, klass)
    assert r.json() == {"rows": 2, "cols": 3, "seats": {"0": str(s1.id), "5": str(s2.id)}}

    # 重存覆盖（缩小表格后超界座位被丢弃）
    r = _put(client, klass, 1, 1, {})
    assert r.status_code == 200
    assert _get(client, klass).json() == {"rows": 1, "cols": 1, "seats": {}}


def test_seating_changes_emit_seat_changed_events(client):
    klass = client["class"]
    s1, s2 = client["students"]["s1"], client["students"]["s2"]

    def seat_events():
        return client["db"].query(Event).filter(Event.type == "seat_changed").all()

    # 初次安排：每位就座学生一条「安排座位」事件（from 为空）
    assert _put(client, klass, 2, 3, {"0": str(s1.id), "5": str(s2.id)}).status_code == 200
    events = seat_events()
    assert len(events) == 2
    by_student = {e.attendees[0].id: e for e in events}
    assert by_student[s1.id].payload["to"] == "第1排第1列"
    assert by_student[s1.id].payload["from"] is None
    assert by_student[s2.id].payload["to"] == "第2排第3列"

    # 重新安排：s1 挪座、s2 移出 → 各留一条；s1 从第2排第3列 → 第1排第2列
    assert _put(client, klass, 2, 3, {"1": str(s1.id)}).status_code == 200
    events = seat_events()
    assert len(events) == 4
    moved = {e.attendees[0].id: e for e in events if e.id not in {x.id for x in events[:2]}}
    s1_ev = moved[s1.id]
    assert s1_ev.payload["from"] == "第1排第1列"
    assert s1_ev.payload["to"] == "第1排第2列"
    s2_ev = moved[s2.id]
    assert s2_ev.payload["from"] == "第2排第3列"
    assert s2_ev.payload["to"] is None  # 移出座位表

    # 无变化的重复保存：不产生新事件
    assert _put(client, klass, 2, 3, {"1": str(s1.id)}).status_code == 200
    assert len(seat_events()) == 4


def test_seating_rejects_duplicate_member_and_out_of_range(client):
    klass = client["class"]
    s1, s2 = client["students"]["s1"], client["students"]["s2"]

    dup = _put(client, klass, 2, 2, {"0": str(s1.id), "1": str(s1.id)})
    assert dup.status_code == 400
    assert "一个学生只能有一个座位" in dup.json()["detail"]

    out_of_range = _put(client, klass, 1, 2, {"5": str(s1.id)})
    assert out_of_range.status_code == 400
    assert "超出表格范围" in out_of_range.json()["detail"]

    non_member = _put(client, klass, 1, 2, {"0": str(client["students"]["outsider"].id)})
    assert non_member.status_code == 400
    assert "不属于这个班级" in non_member.json()["detail"]

    bad_size = _put(client, klass, 0, 2, {})
    assert bad_size.status_code == 422
