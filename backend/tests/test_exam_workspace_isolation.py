"""考试工作区隔离：考试/成绩数据按教师 workspace 完全独立，不跨教师共享。

考试 sitting 与 score Event 都在 payload 里携带 workspace_id（创建时打标，
遗留无标行由 migrate_legacy_workspace 归属给第一位教师）。成绩按
title 前缀 + 日期窗口匹配，因此同名同日的考试在不同工作区必须互不碰撞。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

from app.eventing import create_event
from app.models import Class, Event, Person
from app.payloads import validate_person_payload
from app.security import hash_password
from app.workspace import ensure_workspace_id, migrate_legacy_workspace

from tests.test_scores_events import _headers, _seed_teacher

DAY = "2026-09-17"
SUBJECTS = [{"subject": "math", "full_score": 100}]


def _student(db, name: str, admission_no: str, teacher: Person) -> Person:
    payload = validate_person_payload("student", {"admission_no": admission_no})
    payload["workspace_id"] = ensure_workspace_id(teacher)
    s = Person(name=name, password_hash=hash_password(uuid.uuid4().hex),
               payload=payload)
    db.add(s)
    db.flush()
    return s


def _class(db, name: str, teacher: Person) -> Class:
    c = Class(name=name, academic_year="2026-09", teacher_id=teacher.id)
    db.add(c)
    db.flush()
    return c


def _create_exam(client, headers, name: str = "期中考试", day: str = DAY,
                 class_ids: list[str] | None = None) -> dict:
    body = {"name": name, "exam_date": day, "subjects": SUBJECTS}
    if class_ids is not None:
        body["class_ids"] = class_ids
    r = client.post("/api/exams", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _enter_score(client, headers, exam_id: str, student_id: str, score: float):
    r = client.post(f"/api/exams/{exam_id}/scores", json={
        "student_id": student_id,
        "scores": [{"subject": "math", "score": score}],
    }, headers=headers)
    assert r.status_code == 201, r.text


def test_registered_teacher_starts_empty(client, db):
    """新注册教师从空开始：看不到其他教师工作区的任何考试。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    headers_a = _headers(db, a, "a" * 64)
    _create_exam(client, headers_a)

    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    headers_b = _headers(db, b, "b" * 64)
    r = client.get("/api/exams", headers=headers_b)
    assert r.status_code == 200, r.text
    assert r.json() == []

    r = client.get("/api/exams", headers=headers_a)
    assert [e["name"] for e in r.json()] == ["期中考试"]


def test_cross_teacher_exam_access_forbidden(client, db):
    """详情/修改/删除按工作区校验所有权：他人的考试一律 404。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    headers_a = _headers(db, a, "a" * 64)
    exam = _create_exam(client, headers_a)

    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    headers_b = _headers(db, b, "b" * 64)

    r = client.get(f"/api/exams/{exam['id']}", headers=headers_b)
    assert r.status_code == 404, r.text
    r = client.patch(f"/api/exams/{exam['id']}", json={"name": "改名"},
                     headers=headers_b)
    assert r.status_code == 404, r.text
    r = client.delete(f"/api/exams/{exam['id']}", headers=headers_b)
    assert r.status_code == 404, r.text
    r = client.get(f"/api/exams/{exam['id']}/averages", headers=headers_b)
    assert r.status_code == 404, r.text
    r = client.get(f"/api/exams/{exam['id']}/scores/import-template",
                   headers=headers_b)
    assert r.status_code == 404, r.text


def test_same_name_same_day_scores_isolated(client, db):
    """同名同日的考试在不同工作区互不碰撞：成绩聚合各自独立。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    sa = _student(db, "甲学生", "S001", a)
    headers_a = _headers(db, a, "a" * 64)
    exam_a = _create_exam(client, headers_a)
    _enter_score(client, headers_a, exam_a["id"], str(sa.id), 95)

    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    sb = _student(db, "乙学生", "S002", b)
    headers_b = _headers(db, b, "b" * 64)
    exam_b = _create_exam(client, headers_b)  # 同名同日：必须允许
    _enter_score(client, headers_b, exam_b["id"], str(sb.id), 61)

    # B 的考试均值只统计自己的学生
    r = client.get(f"/api/exams/{exam_b['id']}/averages", headers=headers_b)
    assert r.status_code == 200, r.text
    school = {row["subject"]: row for row in r.json()["school"]}
    assert school["math"]["avg"] == 61.0
    assert school["math"]["count"] == 1

    # A 的考试均值同样只统计自己的学生
    r = client.get(f"/api/exams/{exam_a['id']}/averages", headers=headers_a)
    school = {row["subject"]: row for row in r.json()["school"]}
    assert school["math"]["avg"] == 95.0
    assert school["math"]["count"] == 1

    # 趋势接口也只含各自工作区的考试
    r = client.get("/api/exams/trend", headers=headers_b)
    names = [e["id"] for e in r.json()["exams"]]
    assert names == [exam_b["id"]]


def test_school_wide_exam_attendees_scoped(client, db):
    """不选班级的全校考试：参与者只圈本工作区在读学生。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    sa = _student(db, "甲学生", "S001", a)
    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    _student(db, "乙学生", "S002", b)
    headers_a = _headers(db, a, "a" * 64)

    exam = _create_exam(client, headers_a, name="全校统考", class_ids=[])
    sitting = db.get(Event, uuid.UUID(exam["id"]))
    attendee_ids = {p.id for p in sitting.attendees}
    assert a.id in attendee_ids
    assert sa.id in attendee_ids
    role = Person.payload["role"].as_string()
    others = {
        p.id
        for p in db.query(Person).filter(role == "student").all()
        if (p.payload or {}).get("workspace_id") != ensure_workspace_id(a)
    }
    assert attendee_ids.isdisjoint(others)


def test_create_exam_rejects_foreign_class(client, db):
    """class_ids 传入他人班级时按不存在处理，不能把别人学生圈进自己的考试。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    _class(db, "甲的班", a)
    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    headers_b = _headers(db, b, "b" * 64)

    foreign = db.query(Class).filter(Class.name == "甲的班").one()
    r = client.post("/api/exams", json={
        "name": "期中考试", "exam_date": DAY,
        "subjects": SUBJECTS, "class_ids": [str(foreign.id)],
    }, headers=headers_b)
    assert r.status_code in (400, 404), r.text


def test_enter_scores_rejects_foreign_exam(client, db):
    """不能往他人的考试录入成绩。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    headers_a = _headers(db, a, "a" * 64)
    exam = _create_exam(client, headers_a)

    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    sb = _student(db, "乙学生", "S002", b)
    headers_b = _headers(db, b, "b" * 64)

    r = client.post(f"/api/exams/{exam['id']}/scores", json={
        "student_id": str(sb.id),
        "scores": [{"subject": "math", "score": 88}],
    }, headers=headers_b)
    assert r.status_code == 404, r.text


def test_legacy_untagged_events_claimed_by_first_teacher(client, db):
    """遗留无 workspace 标的考试/成绩在启动迁移时归属第一位教师。"""
    a = _seed_teacher(db, phone="13800000001", email="a@test.example")
    sa = _student(db, "甲学生", "S001", a)
    b = _seed_teacher(db, phone="13800000002", email="b@test.example")
    assert b.id != a.id

    # 直写一条无 workspace 标的遗留 sitting + score（升级前的数据形态）
    create_event(
        db, event_type="exam", title="遗留期中考试",
        start_time=datetime.combine(date(2026, 9, 17), time(9, 0)),
        payload={"full_scores": {"math": 100.0}},
        attendee_ids=[a.id, sa.id],
    )
    create_event(
        db, event_type="score", title="遗留期中考试·math",
        start_time=datetime.combine(date(2026, 9, 17), time(9, 0)),
        payload={"subject": "math", "max_score": 100.0, "score": 77.0},
        attendee_ids=[sa.id],
    )
    db.commit()

    migrate_legacy_workspace(db)
    db.commit()

    headers_a = _headers(db, a, "c" * 64)
    r = client.get("/api/exams", headers=headers_a)
    names = [e["name"] for e in r.json()]
    assert "遗留期中考试" in names


def test_seed_tags_demo_exams(client, db):
    """演示数据打包进 demo 教师工作区：隔离后 demo 账号仍能看到全部 7 次考试。"""
    from app.seed import seed

    seed(db)
    teacher = (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "teacher")
        .order_by(Person.created_at.asc())
        .first()
    )
    headers = _headers(db, teacher, "d" * 64)
    r = client.get("/api/exams", headers=headers)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 7
