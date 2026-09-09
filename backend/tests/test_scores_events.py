"""Behavior lock for the classes/exams/dashboard routers on score Events.

Ports the legacy routers to the event-centric schema: an exam sitting is an
Event(type="exam") titled with the exam name (class_id's students attend),
per-subject full_score config lives in the exam Event's registry-validated
payload as {"full_scores": {subject: score}} — the score-entry flow reads it
to set each score payload's max_score — and scores are per-student score
Events titled "<exam name>·<subject>" dated the exam day. Averages aggregate
payload["score"] over entered rows (absent=true excluded) per sitting =
title prefix + date, attributed to the roster enrolled at the exam date.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timedelta

import pytest

from app import eventing
from app.models import AuthSession, Class, Enrollment, Event, Person
from app.payloads import validate_person_payload
from app.routers import classes as classes_router
from app.routers import dashboard as dashboard_router
from app.routers import exams as exams_router
from app.security import hash_password
from app.workspace import ensure_workspace_id


# ---------------------------------------------------------------------------
# Seed helpers — persons / classes / enrollments / exams / scores
# ---------------------------------------------------------------------------

def _teacher_of(db) -> Person | None:
    """本测试库里（唯一）的教师；工作区隔离后班级/学生的归属锚点。"""
    role = Person.payload["role"].as_string()
    return (
        db.query(Person)
        .filter(role == "teacher")
        .order_by(Person.created_at.asc(), Person.id.asc())
        .first()
    )


def _seed_person(db, name: str, admission_no: str, *, role: str = "student",
                 active: bool = True) -> Person:
    payload = validate_person_payload(role, {"admission_no": admission_no})
    if not active:
        payload["is_active"] = False
    if role == "student":
        # 工作区隔离：学生要挂到教师工作区，该教师的接口才看得到
        teacher = _teacher_of(db)
        if teacher is not None:
            payload["workspace_id"] = ensure_workspace_id(teacher)
    p = Person(name=name, password_hash=hash_password(uuid.uuid4().hex), payload=payload)
    db.add(p)
    db.flush()
    return p


def _seed_teacher(db, phone: str = "13800000001", name: str = "王老师",
                  email: str | None = None) -> Person:
    if email is None:
        email = f"{phone}@test.example"
    p = Person(name=name, phone=phone, email=email,
               password_hash=hash_password("123456"),
               payload=validate_person_payload("teacher", {}))
    ensure_workspace_id(p)
    db.add(p)
    db.flush()
    return p


def _headers(db, person: Person, token: str = "t" * 64) -> dict:
    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def _seed_class(db, name: str = "七年级1班", academic_year: str = "2026") -> Class:
    # 班级归属到教师：工作区隔离后 require_class_in_workspace 校验所有权
    teacher = _teacher_of(db)
    c = Class(name=name, academic_year=academic_year,
              teacher_id=teacher.id if teacher else None)
    db.add(c)
    db.flush()
    return c


def _enroll(db, person: Person, cls: Class, valid_from: date | None = None,
            valid_to: date | None = None, reason: str = "admitted") -> Enrollment:
    row = Enrollment(person_id=person.id, class_id=cls.id,
                     valid_from=valid_from or date.today(), valid_to=valid_to,
                     reason=reason)
    db.add(row)
    db.flush()
    return row


def _create_exam(client, headers, name: str, day: date, subjects: list[dict],
                 class_id: str | None = None) -> dict:
    body = {"name": name, "exam_date": day.isoformat(), "subjects": subjects}
    if class_id is not None:
        body["class_id"] = class_id
    r = client.post("/api/exams", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _enter_scores(db, exam: Event, person: Person, subject_scores: dict[str, float | None]):
    """The score-entry flow: config full_score becomes the payload max_score;
    score None marks an absence (absent=true, no score key)."""
    config = dict(exam.payload["full_scores"])
    day = exam.start_time.date()
    for subject, score in subject_scores.items():
        payload: dict = {"subject": subject, "max_score": config[subject]}
        if score is None:
            payload["absent"] = True
        else:
            payload["score"] = score
        eventing.create_event(
            db, event_type="score", title=f"{exam.title}·{subject}",
            start_time=datetime.combine(day, time(9, 0)),
            payload=payload, attendee_ids=[person.id],
        )
    db.flush()


def _manual_event(db, person: Person, event_type: str, summary: str,
                  start: datetime) -> Event:
    payload = {"summary": summary} if event_type == "home_visited" else {"notes": summary}
    ev = eventing.create_event(db, event_type=event_type, title=summary,
                               start_time=start, payload=payload,
                               attendee_ids=[person.id])
    db.flush()
    return ev


@pytest.fixture()
def headers(db):
    return _headers(db, _seed_teacher(db))


# ---------------------------------------------------------------------------
# fixtures shared by the averaging tests: two classes, two exams, six scores
# ---------------------------------------------------------------------------

@pytest.fixture()
def graded(db, headers, make_client):
    """Class 一班(A, B, C) with 期中考试(语文/数学) + 期末考试(语文), entered:
    A: 90 / absent / 80    B: 70 / 60 / 100    C: no scores."""
    client = make_client(exams_router.router, classes_router.router,
                         dashboard_router.router)
    cls = _seed_class(db)
    a = _seed_person(db, "张一", "S1")
    b = _seed_person(db, "李二", "S2")
    c = _seed_person(db, "王三", "S3")
    for s in (a, b, c):
        _enroll(db, s, cls, valid_from=date(2026, 5, 1))  # enrolled before both exams
    db.commit()  # release the write lock before the API session writes
    e1 = _create_exam(client, headers, "期中考试", date(2026, 5, 20),
                      [{"subject": "语文", "full_score": 100}, {"subject": "数学", "full_score": 100}])
    e2 = _create_exam(client, headers, "期末考试", date(2026, 6, 20),
                      [{"subject": "语文", "full_score": 100}])
    exams = {}
    for row in db.query(Event).filter(Event.type == "exam").all():
        exams[row.title] = row
    _enter_scores(db, exams["期中考试"], a, {"语文": 90, "数学": None})
    _enter_scores(db, exams["期中考试"], b, {"语文": 70, "数学": 60})
    _enter_scores(db, exams["期末考试"], a, {"语文": 80})
    _enter_scores(db, exams["期末考试"], b, {"语文": 100})
    db.commit()
    return {"client": client, "cls": cls, "students": (a, b, c),
            "e1": exams["期中考试"], "e2": exams["期末考试"], "headers": headers}


# ---------------------------------------------------------------------------
# POST /exams — the exam Event
# ---------------------------------------------------------------------------

def test_create_exam_creates_event_with_class_attendees(make_client, db, headers):
    client = make_client(exams_router.router)
    cls = _seed_class(db)
    a = _seed_person(db, "张一", "S1")
    b = _seed_person(db, "李二", "S2")
    for s in (a, b):
        _enroll(db, s, cls)
    _enroll(db, _seed_person(db, "赵四", "S4"), _seed_class(db, "七年级2班"))
    db.commit()

    body = client.post(
        "/api/exams",
        json={"name": "期中考试", "exam_date": "2026-05-20", "class_ids": [str(cls.id)],
              "subjects": [{"subject": "语文", "full_score": 120},
                            {"subject": "数学", "full_score": 100}]},
        headers=headers,
    )
    assert body.status_code == 201, body.text
    data = body.json()
    assert set(data) == {"id", "name", "exam_date", "end_date"}
    assert data["name"] == "期中考试"
    assert data["exam_date"] == "2026-05-20"
    assert data["end_date"] is None  # single-day sitting
    uuid.UUID(data["id"])

    exam = db.get(Event, uuid.UUID(data["id"]))
    assert exam.type == "exam"
    assert exam.title == "期中考试"
    assert exam.start_time.date().isoformat() == "2026-05-20"
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    assert {str(p.id) for p in exam.attendees} == {str(a.id), str(b.id), str(teacher.id)}
    # the per-subject full_score config round-trips through the registry
    assert exam.payload == {"full_scores": {"语文": 120.0, "数学": 100.0}}

    # per-subject color is optional and round-trips next to full_scores
    colored = client.post(
        "/api/exams",
        json={"name": "加试", "exam_date": "2026-07-01",
              "subjects": [{"subject": "物理", "full_score": 100, "color": "#6D5BB8"}]},
        headers=headers,
    )
    assert colored.status_code == 201, colored.text
    colored_exam = db.get(Event, uuid.UUID(colored.json()["id"]))
    assert colored_exam.payload == {
        "full_scores": {"物理": 100.0},
        "subject_colors": {"物理": "#6d5bb8"},
    }
    listed = client.get(f"/api/exams/{colored.json()['id']}", headers=headers).json()
    assert listed["subjects"][0]["color"] == "#6d5bb8"

    # duplicate name on the same date → 409, same Chinese message
    dup = client.post(
        "/api/exams",
        json={"name": "期中考试", "exam_date": "2026-05-20",
              "subjects": [{"subject": "语文", "full_score": 100}]},
        headers=headers,
    )
    assert dup.status_code == 409
    assert dup.json()["detail"] == "该日期已存在同名考试"
    # same name on another date is fine — without class_id the sitting is
    # school-wide, so the whole active student body attends
    db.commit()  # release the read transaction opened by db.get above
    ok = client.post(
        "/api/exams",
        json={"name": "期中考试", "exam_date": "2026-09-20",
              "subjects": [{"subject": "语文", "full_score": 100}]},
        headers=headers,
    )
    assert ok.status_code == 201
    wide = db.get(Event, uuid.UUID(ok.json()["id"]))
    assert {p.payload.get("admission_no") for p in wide.attendees
            if p.role == "student"} == {"S1", "S2", "S4"}
    assert any(p.role == "teacher" for p in wide.attendees)  # the arranger attends


def test_exam_list_and_detail_shapes(make_client, db, headers):
    client = make_client(exams_router.router)
    e1 = _create_exam(client, headers, "期中考试", date(2026, 5, 20),
                      [{"subject": "语文", "full_score": 100}, {"subject": "数学", "full_score": 150}])
    e2 = _create_exam(client, headers, "期末考试", date(2026, 6, 20),
                      [{"subject": "语文", "full_score": 100}])

    rows = client.get("/api/exams", headers=headers).json()
    assert [r["name"] for r in rows] == ["期末考试", "期中考试"]  # exam_date desc
    assert set(rows[0]) == {"id", "name", "exam_date", "end_date", "subjects"}
    assert all(r["end_date"] is None for r in rows)  # both single-day
    zhong = next(r for r in rows if r["id"] == e1["id"])
    assert [s["subject"] for s in zhong["subjects"]] == ["数学", "语文"]  # subject order
    assert zhong["subjects"][0] == {"id": zhong["subjects"][0]["id"], "subject": "数学",
                                    "full_score": 150.0}
    assert {s["id"] for s in zhong["subjects"]} and len({s["id"] for s in zhong["subjects"]}) == 2

    detail = client.get(f"/api/exams/{e1['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["exam_date"] == "2026-05-20"
    assert detail.json()["subjects"] == zhong["subjects"]

    missing = client.get(f"/api/exams/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "exam not found"


def test_create_exam_rejects_duplicate_subjects(make_client, db, headers):
    client = make_client(exams_router.router)
    r = client.post(
        "/api/exams",
        json={"name": "期中考试", "exam_date": "2026-05-20",
              "subjects": [{"subject": "语文", "full_score": 100},
                           {"subject": "语文", "full_score": 120}]},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "科目不能重复"


def test_create_exam_rejects_invalid_color(make_client, db, headers):
    client = make_client(exams_router.router)
    r = client.post(
        "/api/exams",
        json={"name": "期中考试", "exam_date": "2026-05-20",
              "subjects": [{"subject": "语文", "full_score": 100, "color": "red"}]},
        headers=headers,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# class detail / list averages on score events
# ---------------------------------------------------------------------------

def test_class_detail_averages_exclude_absent(graded):
    ctx = graded
    cls, e1, e2 = ctx["cls"], ctx["e1"], ctx["e2"]
    r = ctx["client"].get(f"/api/classes/{cls.id}", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    data = r.json()

    assert set(data) == {"class", "students", "trend", "averages"}
    assert data["class"]["id"] == str(cls.id)
    assert data["class"]["name"] == "七年级1班"
    assert [s["admission_no"] for s in data["students"]] == ["S1", "S2", "S3"]

    # x-axis: every exam event, chronological
    assert [e["id"] for e in data["trend"]["exams"]] == [str(e1.id), str(e2.id)]
    assert [e["exam_date"] for e in data["trend"]["exams"]] == ["2026-05-20", "2026-06-20"]

    # 期中 语文 (90+70)/2=80, 数学 only 60 (absent excluded); 期末 语文 (80+100)/2=90
    assert data["trend"]["series"] == [
        {"subject": "数学", "values": [60.0, None], "full_score": 100.0},
        {"subject": "语文", "values": [80.0, 90.0], "full_score": 100.0},
    ]
    # averages = mean of per-exam means: 语文 (80+90)/2=85 over 2 exams
    assert data["averages"] == [
        {"subject": "数学", "avg": 60.0, "count": 1, "full_score": 100.0},
        {"subject": "语文", "avg": 85.0, "count": 2, "full_score": 100.0},
    ]


def test_class_list_avg_trend_chronological(graded):
    ctx = graded
    cls, e1, e2 = ctx["cls"], ctx["e1"], ctx["e2"]
    rows = ctx["client"].get("/api/classes", headers=ctx["headers"]).json()
    mine = next(r for r in rows if r["id"] == str(cls.id))
    assert mine["student_count"] == 3
    # current-student attribution; entered scores only; ordered by exam date
    assert mine["avg_trend"] == [
        {"exam_id": str(e1.id), "exam_name": "期中考试", "exam_date": "2026-05-20",
         "averages": {"语文": 80.0, "数学": 60.0}},
        {"exam_id": str(e2.id), "exam_name": "期末考试", "exam_date": "2026-06-20",
         "averages": {"语文": 90.0}},
    ]
    # recent_events surfaces record-type events (score events are not records)
    assert all(i["event_type"] not in ("score", "exam") for i in mine["recent_events"])


def test_exam_averages_school_and_classes_exclude_absent(graded):
    ctx = graded
    e1 = ctx["e1"]
    r = ctx["client"].get(f"/api/exams/{e1.id}/averages", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["exam"] == {"id": str(e1.id), "name": "期中考试",
                            "exam_date": "2026-05-20", "end_date": None}
    assert data["school"] == [
        {"subject": "数学", "full_score": 100.0, "avg": 60.0, "min": 60.0,
         "max": 60.0, "count": 1},
        {"subject": "语文", "full_score": 100.0, "avg": 80.0, "min": 70.0,
         "max": 90.0, "count": 2},
    ]
    assert data["classes"] == [
        {"class_id": str(ctx["cls"].id), "class_name": "七年级1班",
         "subject": "数学", "avg": 60.0, "count": 1},
        {"class_id": str(ctx["cls"].id), "class_name": "七年级1班",
         "subject": "语文", "avg": 80.0, "count": 2},
    ]


def test_averages_attribute_by_enrollment_at_exam_date(graded, db):
    """B moves to 二班 on 06-01: 期中 (05-20) stays attributed to 一班, but 期末
    (06-20) splits — while the classes-list avg_trend (current roster) drops B
    from 一班 entirely."""
    ctx = graded
    cls1 = ctx["cls"]
    b = ctx["students"][1]
    cls2 = _seed_class(db, "七年级2班")
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == b.id, Enrollment.class_id == cls1.id)
        .first()
    )
    enrollment.valid_to = date(2026, 6, 1)
    _enroll(db, b, cls2, valid_from=date(2026, 6, 1), reason="moved")
    db.commit()

    e1 = ctx["client"].get(f"/api/exams/{ctx['e1'].id}/averages", headers=ctx["headers"]).json()
    assert e1["classes"] == [  # 05-20 roster: both A and B in 一班
        {"class_id": str(cls1.id), "class_name": "七年级1班", "subject": "数学",
         "avg": 60.0, "count": 1},
        {"class_id": str(cls1.id), "class_name": "七年级1班", "subject": "语文",
         "avg": 80.0, "count": 2},
    ]
    e2 = ctx["client"].get(f"/api/exams/{ctx['e2'].id}/averages", headers=ctx["headers"]).json()
    assert e2["classes"] == [  # 06-20 roster: A in 一班, B in 二班
        {"class_id": str(cls1.id), "class_name": "七年级1班", "subject": "语文",
         "avg": 80.0, "count": 1},
        {"class_id": str(cls2.id), "class_name": "七年级2班", "subject": "语文",
         "avg": 100.0, "count": 1},
    ]

    # class detail trend keeps the per-exam-date attribution
    detail = ctx["client"].get(f"/api/classes/{cls1.id}", headers=ctx["headers"]).json()
    assert detail["trend"]["series"] == [
        {"subject": "数学", "values": [60.0, None], "full_score": 100.0},
        {"subject": "语文", "values": [80.0, 80.0], "full_score": 100.0},
    ]

    # list avg_trend uses the same at-exam-date rule: B counts for 一班 in
    # 期中 (roster on 05-20) but not in 期末 (06-20); 二班 only has 期末
    rows = ctx["client"].get("/api/classes", headers=ctx["headers"]).json()
    mine = next(r for r in rows if r["id"] == str(cls1.id))
    assert mine["avg_trend"] == [
        {"exam_id": str(ctx["e1"].id), "exam_name": "期中考试", "exam_date": "2026-05-20",
         "averages": {"语文": 80.0, "数学": 60.0}},
        {"exam_id": str(ctx["e2"].id), "exam_name": "期末考试", "exam_date": "2026-06-20",
         "averages": {"语文": 80.0}},
    ]
    theirs = next(r for r in rows if r["id"] == str(cls2.id))
    # B joined 二班 on 06-01, so the 期中 sitting isn't attributed to it at all
    assert theirs["avg_trend"] == [
        {"exam_id": str(ctx["e2"].id), "exam_name": "期末考试", "exam_date": "2026-06-20",
         "averages": {"语文": 100.0}},
    ]


def test_exams_trend_orders_by_exam_date(graded):
    ctx = graded
    r = ctx["client"].get("/api/exams/trend", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert [e["name"] for e in data["exams"]] == ["期中考试", "期末考试"]
    assert [e["exam_date"] for e in data["exams"]] == ["2026-05-20", "2026-06-20"]
    assert data["series"] == [
        {"subject": "数学", "values": [60.0, None], "full_score": 100.0},
        {"subject": "语文", "values": [80.0, 90.0], "full_score": 100.0},
    ]


# ---------------------------------------------------------------------------
# PATCH / DELETE exam
# ---------------------------------------------------------------------------

def test_patch_exam_rewrites_score_titles_and_dates(make_client, db, headers):
    client = make_client(exams_router.router)
    cls = _seed_class(db)
    a = _seed_person(db, "张一", "S1")
    _enroll(db, a, cls)
    db.commit()  # release the write lock before the API session writes
    e1 = _create_exam(client, headers, "期中考试", date(2026, 5, 20),
                      [{"subject": "语文", "full_score": 100}])
    exam = db.query(Event).filter(Event.type == "exam").one()
    _enter_scores(db, exam, a, {"语文": 90})
    db.commit()

    r = client.patch(
        f"/api/exams/{e1['id']}",
        json={"name": "期中考试（改）", "exam_date": "2026-05-21"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "期中考试（改）"
    assert data["exam_date"] == "2026-05-21"

    score = db.query(Event).filter(Event.type == "score").one()
    assert score.title == "期中考试（改）·语文"
    assert score.start_time.date().isoformat() == "2026-05-21"

    # averages still resolve after the rewrite
    avg = client.get(f"/api/exams/{e1['id']}/averages", headers=headers).json()
    assert avg["school"] == [{"subject": "语文", "full_score": 100.0, "avg": 90.0,
                              "min": 90.0, "max": 90.0, "count": 1}]

    # subjects structure is frozen once scores exist
    blocked = client.patch(
        f"/api/exams/{e1['id']}",
        json={"subjects": [{"subject": "数学", "full_score": 100}]},
        headers=headers,
    )
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "考试已有成绩录入，无法修改科目结构"

    # a score-less exam can restructure
    db.commit()  # release the read transaction opened by the averages GET
    e2 = _create_exam(client, headers, "期末考试", date(2026, 6, 20),
                      [{"subject": "语文", "full_score": 100}])
    ok = client.patch(
        f"/api/exams/{e2['id']}",
        json={"subjects": [{"subject": "物理", "full_score": 90}]},
        headers=headers,
    )
    assert ok.status_code == 200
    subjects = ok.json()["subjects"]
    assert [s["subject"] for s in subjects] == ["物理"]
    assert subjects[0]["full_score"] == 90.0
    # the structure rewrite lands in the validated payload too
    e2_row = db.get(Event, uuid.UUID(e2["id"]))
    assert e2_row.payload == {"full_scores": {"物理": 90.0}}


def test_delete_exam_keeps_score_events(make_client, db, headers):
    client = make_client(exams_router.router, classes_router.router)
    cls = _seed_class(db)
    a = _seed_person(db, "张一", "S1")
    _enroll(db, a, cls, valid_from=date(2026, 5, 1))
    db.commit()  # release the write lock before the API session writes
    e1 = _create_exam(client, headers, "期中考试", date(2026, 5, 20),
                      [{"subject": "语文", "full_score": 100}])
    exam = db.query(Event).filter(Event.type == "exam").one()
    _enter_scores(db, exam, a, {"语文": 90})
    db.commit()

    r = client.delete(f"/api/exams/{e1['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert db.query(Event).filter(Event.type == "exam").count() == 0
    # score events are individual rows — deleting the sitting keeps them
    assert db.query(Event).filter(Event.type == "score").count() == 1
    # with no sitting to match, the class trend resolves exam_id to None
    rows = client.get("/api/classes", headers=headers).json()
    assert rows[0]["avg_trend"] == [
        {"exam_id": None, "exam_name": "期中考试", "exam_date": "2026-05-20",
         "averages": {"语文": 90.0}},
    ]

    again = client.delete(f"/api/exams/{e1['id']}", headers=headers)
    assert again.status_code == 404
    assert again.json()["detail"] == "exam not found"


# ---------------------------------------------------------------------------
# classes CRUD (unchanged contract, UUID ids)
# ---------------------------------------------------------------------------

def test_class_crud_contract(make_client, db, headers):
    client = make_client(classes_router.router)
    student = _seed_person(db, "张一", "S1")
    db.commit()

    r = client.post("/api/classes", json={
        "name": "七年级1班", "academic_year": "2026",
    }, headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data == {
        "id": data["id"], "name": "七年级1班",
        "academic_year": "2026", "student_count": 0, "students": [],
    }

    dup = client.post("/api/classes", json={
        "name": "七年级1班", "academic_year": "2026",
    }, headers=headers)
    assert dup.status_code == 409
    assert dup.json()["detail"] == "该学年已存在同名班级"

    _enroll(db, student, db.get(Class, uuid.UUID(data["id"])))
    db.commit()
    patched = client.patch(f"/api/classes/{data['id']}", json={
        "name": "七年级1班", "academic_year": "2026/2027",
    }, headers=headers)
    assert patched.status_code == 200
    assert patched.json()["academic_year"] == "2026/2027"
    assert patched.json()["student_count"] == 1

    conflict = client.delete(f"/api/classes/{data['id']}", headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "班级内仍有学生或历史记录，无法删除"

    empty = client.post("/api/classes", json={
        "name": "七年级3班", "academic_year": "2026",
    }, headers=headers)
    assert empty.status_code == 201
    gone = client.delete(f"/api/classes/{empty.json()['id']}", headers=headers)
    assert gone.status_code == 200
    assert gone.json() == {"ok": True}

    missing = client.get(f"/api/classes/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "class not found"


# ---------------------------------------------------------------------------
# dashboard: calendar + summary
# ---------------------------------------------------------------------------

def test_calendar_range_and_kinds(graded, db):
    ctx = graded
    a = ctx["students"][0]
    _manual_event(db, a, "home_visited", "6月家访", datetime(2026, 6, 5, 10, 0))
    _manual_event(db, a, "talk", "七月谈话", datetime(2026, 7, 1, 9, 0))
    db.commit()

    r = ctx["client"].get("/api/calendar", params={"year": 2026, "month": 6},
                          headers=ctx["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["year"] == 2026 and data["month"] == 6
    items = data["items"]
    assert [i["date"] for i in items] == ["2026-06-05", "2026-06-20"]  # date sort
    visit, exam = items
    assert exam["kind"] == "exam"
    assert exam["id"] == str(ctx["e2"].id)
    assert exam["name"] == "期末考试"
    assert visit["kind"] == "record"
    assert visit["event_type"] == "home_visited"
    assert visit["student_id"] == str(a.id)
    assert visit["student_name"] == "张一"
    assert visit["payload"] == {"summary": "6月家访"}
    # graded fixture students have no birth_date, so June calendar has no birthdays
    assert all(i.get("event_type") != "birthday" for i in items)

    bad = ctx["client"].get("/api/calendar", params={"year": 2026, "month": 13},
                            headers=ctx["headers"])
    assert bad.status_code == 400
    assert bad.json()["detail"] == "month out of range"


def test_dashboard_summary_counts_and_panels(graded, db):
    ctx = graded
    client, a, b = ctx["client"], ctx["students"][0], ctx["students"][1]
    _manual_event(db, a, "home_visited", "家访甲", datetime(2026, 6, 5, 10, 0))
    _manual_event(db, a, "home_visited", "家访乙", datetime(2026, 6, 6, 10, 0))
    _manual_event(db, b, "note_added", "课堂随笔", datetime(2026, 6, 7, 10, 0))
    # the recording teacher attends the visit too — digest rows stay
    # student-centric: teacher/guardian attendees never surface as a row
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    eventing.create_event(
        db, event_type="home_visited", title="家访丙",
        start_time=datetime(2026, 6, 8, 10, 0),
        payload={"summary": "有老师同行的家访"},
        attendee_ids=[b.id, teacher.id],
    )
    db.commit()  # release the write lock before the API session writes
    future1 = _create_exam(client, ctx["headers"], "十月月考",
                           date.today() + timedelta(days=30),
                           [{"subject": "语文", "full_score": 100}])
    future2 = _create_exam(client, ctx["headers"], "十一月月考",
                           date.today() + timedelta(days=60),
                           [{"subject": "语文", "full_score": 100}])
    db.commit()

    r = client.get("/api/dashboard", headers=ctx["headers"])
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["name"] == "王老师"
    assert data["counts"] == {"students": 3, "classes": 1, "exams": 4, "interactions": 4}

    assert [e["name"] for e in data["upcoming_exams"]] == ["十月月考", "十一月月考"]
    assert data["upcoming_exams"][0]["exam_date"] == (date.today() + timedelta(days=30)).isoformat()

    # recent events: one row per Event with its student roster (score/exam
    # rows are not digest items; the attending teacher never surfaces)
    types = [e["event_type"] for e in data["recent_events"]]
    assert "score" not in types and "exam" not in types
    assert set(types) <= {"home_visited", "note_added"}
    roster_names = {s["name"] for e in data["recent_events"] for s in e["students"]}
    assert roster_names <= {"张一", "李二", "王三"}
    assert all(e["title"] for e in data["recent_events"])
    newest = data["recent_events"][0]
    assert newest["title"] == "家访丙"
    assert [s["name"] for s in newest["students"]] == ["李二"]
    assert newest["payload"]["summary"] == "有老师同行的家访"
