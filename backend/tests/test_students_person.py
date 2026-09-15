"""Behavior lock for the students router on Person payloads + Event timeline.

Ports the scenarios of the legacy students tests to the event-centric schema:
ids become UUID strings, Student columns live in person.payload, StudentEvent
rows become Event rows linked through person_events, and birthdays are no
longer persisted — GET /students/{id}/timeline synthesizes the next occurrence
from payload["birth_date"]. Score "results" are per-subject score Events whose
title is "<exam name>·<subject>"; PATCH /results/{id} edits such an Event's
payload (absent convention: absent=true and no score key).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest

from app import eventing
from app.eventing import MANUAL_EVENT_TYPES, next_birthday_date, sync_birthday_event
from app.models import AuthSession, Class, Enrollment, Event, Person, Tag, person_tags, student_guardians
from app.routers.students import AUTO_HOME_VISIT_TAG_NAME
from app.payloads import validate_person_payload
from app.routers import dashboard, students
from app.security import hash_password
from app.workspace import ensure_workspace_id


# ---------------------------------------------------------------------------
# Seed helpers — persons / classes / enrollments / events, straight on the db
# ---------------------------------------------------------------------------

def _teacher_of(db) -> Person | None:
    role = Person.payload["role"].as_string()
    return (
        db.query(Person)
        .filter(role == "teacher")
        .order_by(Person.created_at.asc(), Person.id.asc())
        .first()
    )


def _seed_person(db, name: str, admission_no: str, *, birth_date: str | None = None,
                 active: bool = True) -> Person:
    # `name` is a typed person column; the payload carries only student data
    payload = validate_person_payload("student", {"admission_no": admission_no})
    if birth_date:
        payload["birth_date"] = birth_date
    if not active:
        payload["is_active"] = False
    teacher = _teacher_of(db)
    if teacher is not None:
        payload["workspace_id"] = ensure_workspace_id(teacher)
    p = Person(name=name, password_hash=hash_password(uuid.uuid4().hex), payload=payload)
    db.add(p)
    db.flush()
    return p


def _seed_teacher(db, phone: str = "13800000001", email: str | None = None) -> Person:
    if email is None:
        email = f"{phone}@test.example"
    p = Person(name="王老师", phone=phone, email=email,
               password_hash=hash_password("123456"),
               payload=validate_person_payload("teacher", {}))
    ensure_workspace_id(p)
    db.add(p)
    db.flush()
    return p


def _seed_guardian(db, name: str, phone: str) -> Person:
    """A guardian is a Person too — link it to a student through student_guardians."""
    g = Person(name=name, phone=phone, password_hash=hash_password(uuid.uuid4().hex),
               payload=validate_person_payload("guardian", {"phone": phone}))
    db.add(g)
    db.flush()
    return g


def _headers(db, person: Person, token: str = "t" * 64) -> dict:
    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def _seed_class(db, name: str = "七年级1班") -> Class:
    teacher = _teacher_of(db)
    c = Class(name=name, academic_year="2026",
              teacher_id=teacher.id if teacher else None)
    db.add(c)
    db.flush()
    return c


def _enroll(db, person: Person, cls: Class, reason: str = "admitted") -> Enrollment:
    row = Enrollment(person_id=person.id, class_id=cls.id,
                     valid_from=date.today(), reason=reason)
    db.add(row)
    db.flush()
    return row


def _score_event(db, person: Person, exam_name: str, subject: str, *, score: float | None = None,
                 max_score: float = 100.0, absent: bool = False,
                 start: datetime | None = None) -> Event:
    payload: dict = {"subject": subject, "max_score": max_score}
    if absent:
        payload["absent"] = True
    else:
        payload["score"] = score
    ev = eventing.create_event(
        db, event_type="score", title=f"{exam_name}·{subject}",
        start_time=start or datetime(2026, 5, 20, 9, 0),
        payload=payload, attendee_ids=[person.id],
    )
    db.flush()
    return ev


def _manual_event(db, person: Person, event_type: str, summary: str,
                  start: datetime, *, title: str | None = None) -> Event:
    if event_type == "home_visited":
        payload = {"summary": summary}
    elif event_type == "comment":
        payload = {
            "notes": summary,
            "about": {"id": str(person.id), "name": person.name},
        }
    else:
        raise ValueError(f"unsupported manual event type: {event_type}")
    ev = eventing.create_event(
        db, event_type=event_type, title=title or summary,
        start_time=start, payload=payload, attendee_ids=[person.id],
    )
    db.flush()
    return ev


@pytest.fixture()
def headers(db):
    return _headers(db, _seed_teacher(db))


# ---------------------------------------------------------------------------
# list / create / get
# ---------------------------------------------------------------------------

def test_list_students_admission_no_order_and_shape(make_client, db, headers):
    cls = _seed_class(db)
    s2 = _seed_person(db, "李二", "S2")
    s10 = _seed_person(db, "王十", "S10")
    s1 = _seed_person(db, "张一", "S1")
    for s in (s2, s10, s1):
        _enroll(db, s, cls)
    db.commit()

    r = make_client(students.router).get("/api/students", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    # plain string ordering, same as the old order_by(Student.admission_no)
    assert [row["admission_no"] for row in rows] == ["S1", "S10", "S2"]
    assert set(rows[0]) == {"id", "admission_no", "name", "gender", "status",
                            "class", "guardians", "last_exam", "last_event", "tags"}
    assert rows[0]["name"] == "张一"
    assert rows[0]["status"] == "active"
    assert rows[0]["class"] == {"id": str(cls.id), "name": cls.name}
    assert rows[0]["last_exam"] is None
    assert rows[0]["last_event"] is None
    assert rows[0]["tags"] == []
    uuid.UUID(rows[0]["id"])


def test_list_students_last_event(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S001")
    _enroll(db, s, cls)
    _manual_event(db, s, "home_visited", "开学家访", datetime(2026, 3, 15, 19, 0))
    db.commit()

    r = make_client(students.router).get("/api/students", headers=headers)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json() if x["id"] == str(s.id))
    last = row["last_event"]
    assert set(last) == {"id", "event_type", "occurred_at", "payload"}
    assert last["event_type"] == "home_visited"
    assert last["payload"]["summary"] == "开学家访"


def test_list_students_last_event_personal_only(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S002")
    _enroll(db, s, cls)
    _manual_event(db, s, "comment", "期末评语", datetime(2026, 3, 22, 9, 0))
    _score_event(db, s, "期中考试", "math", score=88.0)
    db.commit()

    r = make_client(students.router).get("/api/students", headers=headers)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json() if x["id"] == str(s.id))
    assert row["last_event"]["event_type"] == "comment"
    assert row["last_event"]["payload"]["notes"] == "期末评语"
    assert row["last_exam"] is not None


def test_create_student_201_old_keys_seeds_payload_enrollment_enrolled_event(make_client, db, headers):
    cls = _seed_class(db)
    _seed_person(db, "老的", "S7")  # admission_no scans digits → next is S8
    db.commit()

    r = make_client(students.router).post(
        "/api/students",
        json={"name": "  林新  ", "gender": "female", "birth_date": "2013-06-01",
              "guardian_name": "林爸爸", "guardian_phone": "13810001000",
              "address": "幸福路1号", "class_id": str(cls.id)},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"id", "admission_no", "name"}
    assert body["admission_no"] == "S8"
    assert body["name"] == "林新"  # stripped

    person = db.get(Person, uuid.UUID(body["id"]))
    assert person is not None
    assert person.name == "林新"
    assert person.payload["admission_no"] == "S8"
    assert person.payload["birth_date"] == "2013-06-01"
    assert person.payload["gender"] == "F"
    assert person.payload["is_active"] is True

    # the guardian is a Person linked through student_guardians, not a flat
    # student payload key
    linked = (
        db.query(Person)
        .join(student_guardians, student_guardians.c.guardian_id == Person.id)
        .filter(student_guardians.c.student_id == person.id)
        .all()
    )
    assert [g.name for g in linked] == ["林爸爸"]

    enrollments = db.query(Enrollment).filter(Enrollment.person_id == person.id).all()
    assert len(enrollments) == 1 and enrollments[0].class_id == cls.id
    assert enrollments[0].valid_to is None

    events = db.query(Event).filter(Event.attendees.any(Person.id == person.id)).all()
    assert sorted(e.type for e in events) == ["birthday", "enrolled"]
    assert events[0].payload == {"class_name": cls.name}


def test_create_student_class_not_found_400(make_client, db, headers):
    r = make_client(students.router).post(
        "/api/students",
        json={"name": " nobody", "class_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "class not found"


def test_create_student_without_class_enrolls_unassigned(make_client, db, headers):
    r = make_client(students.router).post(
        "/api/students",
        json={"name": "待分班"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    person = db.get(Person, uuid.UUID(r.json()["id"]))
    assert db.query(Enrollment).filter(Enrollment.person_id == person.id).count() == 1

    listed = make_client(students.router).get("/api/students", headers=headers).json()
    row = next(item for item in listed if item["id"] == r.json()["id"])
    assert row["class"] is None


def test_assign_from_unassigned_records_join_class_event(make_client, db, headers):
    client = make_client(students.router)
    r = client.post("/api/students", json={"name": "待分班"}, headers=headers)
    assert r.status_code == 201, r.text
    s_id = uuid.UUID(r.json()["id"])
    cls = _seed_class(db, "七年级1班")
    db.commit()

    r = client.patch(f"/api/students/{s_id}", json={"class_id": str(cls.id)}, headers=headers)
    assert r.status_code == 200, r.text
    moved = (
        db.query(Event)
        .filter(Event.type == "class_moved", Event.attendees.any(Person.id == s_id))
        .one()
    )
    assert moved.title == "加入班级"
    assert moved.payload.get("from_class") is None
    assert moved.payload["to_class"] == cls.name


def test_get_student_shape_scores_and_404(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    _enroll(db, s, cls)
    _score_event(db, s, "期中考试", "math", score=90.0)
    _score_event(db, s, "期中考试", "english", absent=True)
    _score_event(db, s, "月考", "math", score=80.0,
                 start=datetime(2026, 4, 1, 9, 0))
    db.commit()
    client = make_client(students.router)

    r = client.get(f"/api/students/{s.id}", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"id", "admission_no", "name", "gender", "birth_date",
                         "guardians", "address", "status",
                         "class", "scores", "tags"}
    assert body["birth_date"] == "2012-05-14"
    assert body["class"] == {"id": str(cls.id), "name": cls.name}
    # ordered by (start_time, subject): 月考 math, 期中 english, 期中 math
    assert [(row["exam_name"], row["subject"]) for row in body["scores"]] == [
        ("月考", "math"), ("期中考试", "english"), ("期中考试", "math")]
    row = body["scores"][2]
    assert set(row) == {"result_id", "exam_id", "exam_name", "exam_date",
                        "subject", "subject_color", "score", "full_score", "status"}
    assert row["result_id"] and row["score"] == 90.0
    assert row["full_score"] == 100.0  # from payload max_score
    assert row["exam_date"] == "2026-05-20"  # from score event start_time
    assert row["status"] == "entered"
    absent_row = body["scores"][1]
    assert absent_row["score"] is None and absent_row["status"] == "absent"

    r = client.get(f"/api/students/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "student not found"


# ---------------------------------------------------------------------------
# patch / delete
# ---------------------------------------------------------------------------

def test_patch_student_partial_merge_keeps_other_payload_keys(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    g = _seed_guardian(db, "林爸爸", "13810001000")
    db.execute(student_guardians.insert().values(student_id=s.id, guardian_id=g.id))
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/students/{s.id}", json={"address": "幸福路1号"},
                     headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"id", "admission_no", "name", "gender", "status", "class"}
    db.refresh(s)
    assert s.payload["address"] == "幸福路1号"
    # partial patch must not drop sibling payload keys or the name column
    assert s.payload["birth_date"] == "2012-05-14"
    assert s.payload["admission_no"] == "S001"
    assert s.name == "林晓雨"

    r = client.patch(f"/api/students/{uuid.UUID(int=1)}", json={"address": "x"},
                     headers=headers)
    assert r.status_code == 404


def test_patch_student_admission_no_unique(make_client, db, headers):
    s1 = _seed_person(db, "甲", "S001")
    s2 = _seed_person(db, "乙", "S002")
    db.commit()
    client = make_client(students.router)

    r = client.patch(
        f"/api/students/{s1.id}",
        json={"admission_no": "2025070701"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["admission_no"] == "2025070701"
    db.refresh(s1)
    assert s1.payload["admission_no"] == "2025070701"

    r = client.patch(
        f"/api/students/{s2.id}",
        json={"admission_no": "2025070701"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "学号已被使用"

    r = client.patch(
        f"/api/students/{s1.id}",
        json={"admission_no": "2025070701"},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_patch_student_status_and_class_move(make_client, db, headers):
    c1 = _seed_class(db, "七年级1班")
    c2 = _seed_class(db, "七年级2班")
    s = _seed_person(db, "林晓雨", "S001")
    _enroll(db, s, c1)
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/students/{s.id}", json={"status": "inactive"},
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "inactive"
    db.refresh(s)
    assert s.payload["is_active"] is False

    r = client.patch(f"/api/students/{s.id}", json={"status": "bogus"},
                     headers=headers)
    assert r.status_code == 400

    r = client.patch(f"/api/students/{s.id}", json={"class_id": str(c2.id)},
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["class"] == {"id": str(c2.id), "name": c2.name}
    rows = (db.query(Enrollment).filter(Enrollment.person_id == s.id)
            .order_by(Enrollment.valid_from).all())
    assert len(rows) == 2
    assert rows[0].valid_to is not None and rows[1].valid_to is None
    assert rows[1].class_id == c2.id
    moved = (db.query(Event).filter(Event.type == "class_moved",
                                    Event.attendees.any(Person.id == s.id)).one())
    assert moved.payload["from_class"] == c1.name
    assert moved.payload["to_class"] == c2.name
    assert moved.title == "转班"

    r = client.patch(f"/api/students/{s.id}", json={"class_id": str(uuid.uuid4())},
                     headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "class not found"


def test_delete_student_soft_deactivates_when_score_events_exist(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S001")
    _enroll(db, s, cls)
    _score_event(db, s, "期中考试", "math", score=90.0)
    db.commit()
    client = make_client(students.router)

    r = client.delete(f"/api/students/{s.id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "action": "deactivated"}

    db.refresh(s)
    assert s.payload["is_active"] is False
    enrollments = db.query(Enrollment).filter(Enrollment.person_id == s.id).all()
    assert enrollments[0].valid_to is not None
    comments = (db.query(Event).filter(Event.type == "comment",
                                       Event.attendees.any(Person.id == s.id)).all())
    assert comments[-1].title == "账号停用"
    assert comments[-1].payload["notes"] == "账号停用"
    assert db.get(Person, s.id) is not None


def test_delete_student_hard_deletes_when_no_written_evidence(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S001")
    _enroll(db, s, cls)
    eventing.create_event(db, event_type="enrolled", title="入学",
                          start_time=datetime(2026, 2, 20, 9, 0),
                          payload={"class_name": cls.name},
                          attendee_ids=[s.id])
    db.commit()
    client = make_client(students.router)

    r = client.delete(f"/api/students/{s.id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "action": "deleted"}
    assert db.query(Person).filter(Person.id == s.id).first() is None
    assert db.query(Enrollment).filter(Enrollment.person_id == s.id).count() == 0
    assert db.query(Event).count() == 0  # enrolled event went with the student

    r = client.delete(f"/api/students/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "student not found"


# ---------------------------------------------------------------------------
# tags
# ---------------------------------------------------------------------------

def test_tag_attach_detach_and_unused_prune(make_client, db, headers):
    s1 = _seed_person(db, "林晓雨", "S001")
    s2 = _seed_person(db, "王小明", "S002")
    db.commit()
    client = make_client(students.router)

    r = client.post(f"/api/students/{s1.id}/tags",
                    json={"name": " 需要关注 ", "color": "#FF0000"},
                    headers=headers)
    assert r.status_code == 201, r.text
    tag = r.json()
    assert set(tag) == {"id", "name", "color"}
    assert tag["name"] == "需要关注" and tag["color"] == "#ff0000"

    # same name+color reuses the tag row; attaching again is a 409
    r = client.post(f"/api/students/{s2.id}/tags",
                    json={"name": "需要关注", "color": "#ff0000"}, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == tag["id"]
    r = client.post(f"/api/students/{s1.id}/tags",
                    json={"name": "需要关注", "color": "#ff0000"}, headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == "该标签已添加"

    r = client.post(f"/api/students/{s1.id}/tags",
                    json={"name": "x", "color": "red"}, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "颜色格式不正确"
    r = client.post(f"/api/students/{s1.id}/tags",
                    json={"name": "  ", "color": "#ff0000"}, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "tag name is required"
    r = client.post(f"/api/students/{uuid.uuid4()}/tags",
                    json={"name": "x", "color": "#ff0000"}, headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "student not found"

    # usage counts drive /tags ordering
    r = client.get("/api/tags", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    assert set(rows[0]) == {"id", "name", "color", "usage"}
    assert rows[0]["usage"] == 2

    r = client.delete(f"/api/students/{s1.id}/tags/{tag['id']}", headers=headers)
    assert r.status_code == 204
    r = client.delete(f"/api/students/{s1.id}/tags/{tag['id']}", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "tag not attached"

    # last detach prunes the now-unused tag row
    client.delete(f"/api/students/{s2.id}/tags/{tag['id']}", headers=headers)
    assert db.query(Tag).count() == 0
    assert client.get("/api/tags", headers=headers).json() == []


# ---------------------------------------------------------------------------
# timeline (manual events + projected birthday) and manual-event CRUD
# ---------------------------------------------------------------------------

TIMELINE_KEYS = {"id", "title", "event_type", "occurred_at", "actor", "payload",
                 "actor_teacher_id", "is_system"}


def test_timeline_lists_manual_events_and_birthday_event(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    sync_birthday_event(db, s)
    _manual_event(db, s, "home_visited", "开学前家访", datetime(2026, 3, 15, 19, 0))
    _manual_event(db, s, "comment", "聊了作业习惯", datetime(2026, 4, 1, 12, 0))
    _score_event(db, s, "期中考试", "math", score=90.0)  # scores live in the 成绩 card
    db.commit()
    client = make_client(students.router)

    r = client.get(f"/api/students/{s.id}/timeline", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert {it["event_type"] for it in items} == {"comment", "home_visited", "birthday"}
    for it in items:
        assert set(it) == TIMELINE_KEYS

    comment = next(it for it in items if it["event_type"] == "comment")
    assert comment["title"] == "聊了作业习惯"
    assert comment["payload"]["notes"] == "聊了作业习惯"
    assert comment["is_system"] is False

    bday = next(it for it in items if it["event_type"] == "birthday")
    expected = next_birthday_date(date(2012, 5, 14))
    assert bday["occurred_at"] == datetime.combine(expected, datetime.min.time().replace(hour=9)).isoformat()
    assert bday["payload"] == {"birth_date": "2012-05-14"}
    assert bday["is_system"] is True
    assert db.query(Event).filter(Event.type == "birthday").count() == 1

    r = client.get(f"/api/students/{uuid.uuid4()}/timeline", headers=headers)
    assert r.status_code == 404


def test_manual_event_create_list_patch_delete(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001")
    other = _seed_person(db, "王小明", "S002")
    eventing.create_event(db, event_type="enrolled", title="入学",
                          start_time=datetime(2026, 2, 20, 9, 0),
                          payload={"class_name": "七年级1班"}, attendee_ids=[s.id])
    db.commit()
    client = make_client(students.router)

    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "purpose": "开学沟通",
                          "summary": "开学前沟通",
                          "occurred_at": "2026-04-01T12:00:00"},
                    headers=headers)
    assert r.status_code == 201, r.text
    created = r.json()
    assert set(created) == {"id", "status"}
    assert created["status"] == "created"
    ev = db.get(Event, uuid.UUID(created["id"]))
    assert ev.type == "home_visited"
    assert ev.payload == {"purpose": "开学沟通", "summary": "开学前沟通"}

    # home visit maps purpose/summary onto the home_visited payload
    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "purpose": "开学沟通",
                          "summary": "开学前家访"},
                    headers=headers)
    assert r.status_code == 201, r.text
    visit = db.get(Event, uuid.UUID(r.json()["id"]))
    assert visit.payload == {"purpose": "开学沟通", "summary": "开学前家访"}

    r = client.get(f"/api/students/{s.id}/events", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["event_type"] for row in rows] == ["home_visited", "home_visited"]
    assert set(rows[0]) == {"id", "event_type", "occurred_at", "actor", "payload"}
    # the enrolled (system) event never shows in the manual-record list
    assert all(row["event_type"] != "enrolled" for row in rows)

    r = client.get(f"/api/students/{s.id}/events/{created['id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["event_type"] == "home_visited"

    r = client.patch(f"/api/students/{s.id}/events/{created['id']}",
                     json={"event_type": "home_visited", "summary": "改：开学前沟通",
                           "occurred_at": "2026-04-02T12:00:00"},
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": created["id"], "status": "updated"}
    db.refresh(ev)
    assert ev.payload["summary"] == "改：开学前沟通"
    assert ev.start_time == datetime(2026, 4, 2, 12, 0)

    # enrolled events: date and notes editable; type stays system-generated
    enrolled_id = db.query(Event).filter(Event.type == "enrolled").one().id
    r = client.patch(
        f"/api/students/{s.id}/events/{enrolled_id}",
        json={
            "event_type": "enrolled",
            "summary": "2025 年秋季入学",
            "occurred_at": "2025-09-01T08:00:00",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    enrolled = db.get(Event, enrolled_id)
    assert enrolled.payload["notes"] == "2025 年秋季入学"
    assert enrolled.start_time == datetime(2025, 9, 1, 8, 0)

    r = client.patch(
        f"/api/students/{s.id}/events/{enrolled_id}",
        json={"event_type": "exam", "summary": "x"},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "cannot change system event type"

    class_moved = db.query(Event).filter(Event.type == "class_moved").first()
    if class_moved:
        r = client.patch(
            f"/api/students/{s.id}/events/{class_moved.id}",
            json={
                "event_type": "class_moved",
                "summary": "调至初二三班",
                "occurred_at": "2026-03-01T09:00:00",
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        db.refresh(class_moved)
        assert class_moved.payload["notes"] == "调至初二三班"
        assert class_moved.start_time == datetime(2026, 3, 1, 9, 0)

    r = client.delete(f"/api/students/{s.id}/events/{enrolled_id}", headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "system events cannot be deleted"

    # an event of another student is a 404 on both read and delete
    r = client.get(f"/api/students/{other.id}/events/{created['id']}", headers=headers)
    assert r.status_code == 404
    r = client.delete(f"/api/students/{s.id}/events/{created['id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "deleted"}
    assert db.query(Event).filter(Event.id == uuid.UUID(created["id"])).first() is None


# ---------------------------------------------------------------------------
# /records, /teachers/me/event-types
# ---------------------------------------------------------------------------

def test_events_lists_events_the_teacher_attends(make_client, db, headers):
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    s1_payload = validate_person_payload("student", {"admission_no": "S001"})
    s1_payload["workspace_id"] = ensure_workspace_id(teacher)
    s1 = Person(name="林晓雨", password_hash=hash_password(uuid.uuid4().hex),
                payload=s1_payload)
    db.add(s1)
    db.flush()
    # a guardian Person of record, linked through student_guardians — the home
    # visit snapshots its name into the event payload
    g1 = Person(name="林女士", phone="13810001000",
                password_hash=hash_password(uuid.uuid4().hex),
                payload=validate_person_payload("guardian", {"phone": "13810001000"}))
    db.add(g1)
    db.flush()
    db.execute(student_guardians.insert().values(student_id=s1.id, guardian_id=g1.id))
    s2 = _seed_person(db, "王小明", "S002")
    db.commit()  # the API session must see the new students
    client = make_client(students.router)

    # events the teacher creates involve student + teacher, and a home visit
    # snapshots the guardian of record into its payload
    r = client.post(f"/api/students/{s1.id}/events",
                    json={"event_type": "home_visited", "summary": "开学前家访",
                          "occurred_at": "2026-03-15T19:00:00"},
                    headers=headers)
    assert r.status_code == 201, r.text
    r = client.post("/api/comments",
                    json={"student_id": str(s2.id), "notes": "作业潦草",
                          "occurred_at": "2026-03-20T09:00:00"},
                    headers=headers)
    assert r.status_code == 201, r.text

    _score_event(db, s1, "期中考试", "math", score=90.0)  # student-only, not hers
    other = _seed_teacher(db, phone="13800000002")
    other_headers = _headers(db, other, token="o" * 64)
    r = make_client(students.router).post(
        f"/api/students/{s2.id}/events",
        json={"event_type": "home_visited", "summary": "另一位老师的家访",
              "occurred_at": "2026-03-21T10:00:00"},
        headers=other_headers)
    assert r.status_code == 201, r.text
    db.commit()

    r = client.get("/api/events", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    # only the signed-in teacher's own events, newest first
    assert [(row["event_type"], row["student_name"]) for row in rows] == [
        ("comment", "王小明"), ("home_visited", "林晓雨")]
    assert set(rows[0]) == {"id", "title", "student_id", "student_name",
                            "students", "whole_classes", "event_type",
                            "occurred_at", "actor", "payload"}
    assert rows[0]["student_id"] == str(s2.id)
    assert rows[0]["students"] == [
        {"id": str(s2.id), "name": "王小明", "class_name": None}
    ]
    assert rows[0]["title"] == "作业潦草"
    assert rows[0]["payload"]["notes"] == "作业潦草"
    visit = rows[1]
    assert visit["title"] == "开学前家访"
    assert visit["payload"] == {"purpose": "例行家访", "summary": "开学前家访", "guardian": "林女士"}
    # the type param narrows the feed (the 家访 page reads home_visited only)
    r = client.get("/api/events?type=home_visited", headers=headers)
    assert [(row["event_type"], row["student_name"]) for row in r.json()] == [
        ("home_visited", "林晓雨")]
    # both records carry the teacher as an attendee alongside the student;
    # the visit's fallback guardian-of-record attends too
    for row in rows:
        ev = db.get(Event, uuid.UUID(row["id"]))
        expected = {s2.id if row is rows[0] else s1.id, teacher.id}
        if row is rows[1]:
            expected.add(g1.id)
        assert {p.id for p in ev.attendees} == expected


def test_home_visit_guardian_participants(make_client, db, headers):
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    s_payload = validate_person_payload("student", {"admission_no": "S001"})
    s_payload["workspace_id"] = ensure_workspace_id(teacher)
    s = Person(name="林晓雨", password_hash=hash_password(uuid.uuid4().hex),
               payload=s_payload)
    db.add(s)
    db.flush()
    g_mom = Person(name="林女士", phone="13810001000",
                   password_hash=hash_password(uuid.uuid4().hex),
                   payload=validate_person_payload("guardian", {"phone": "13810001000"}))
    g_dad = Person(name="林先生", phone="13810001001",
                   password_hash=hash_password(uuid.uuid4().hex),
                   payload=validate_person_payload("guardian", {"phone": "13810001001"}))
    db.add_all([g_mom, g_dad])
    db.flush()
    db.execute(student_guardians.insert().values(student_id=s.id, guardian_id=g_mom.id))
    db.execute(student_guardians.insert().values(student_id=s.id, guardian_id=g_dad.id))
    stranger = Person(name="路人", phone="13810001999",
                      password_hash=hash_password(uuid.uuid4().hex),
                      payload=validate_person_payload("guardian", {"phone": "13810001999"}))
    db.add(stranger)
    db.commit()
    client = make_client(students.router)

    # selected guardians attend the visit and their names ride in the payload
    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "summary": "开学前家访",
                          "guardian_ids": [str(g_dad.id), str(g_mom.id)]},
                    headers=headers)
    assert r.status_code == 201, r.text
    ev = db.get(Event, uuid.UUID(r.json()["id"]))
    assert {p.id for p in ev.attendees} == {s.id, g_mom.id, g_dad.id, teacher.id}
    assert ev.payload["guardian"] == "林先生、林女士"

    # explicit empty selection: no guardian attended, no snapshot
    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "summary": "学生独自在家",
                          "guardian_ids": []},
                    headers=headers)
    assert r.status_code == 201, r.text
    ev2 = db.get(Event, uuid.UUID(r.json()["id"]))
    assert "guardian" not in ev2.payload
    assert {p.role for p in ev2.attendees} == {"student", "teacher"}

    # a guardian person not linked to this student is rejected
    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "summary": "x",
                          "guardian_ids": [str(stranger.id)]},
                    headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "监护人不属于该学生"


def test_home_visit_mark_done_adds_tag(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001")
    db.commit()
    client = make_client(students.router)
    r = client.post(
        f"/api/students/{s.id}/events",
        json={"event_type": "home_visited", "summary": "开学前家访"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    ev_id = r.json()["id"]

    r = client.patch(
        f"/api/students/{s.id}/events/{ev_id}",
        json={"event_type": "home_visited", "summary": "开学前家访", "done": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    ev = db.get(Event, uuid.UUID(ev_id))
    assert ev.payload.get("done") is True
    tag = db.query(Tag).filter(Tag.name == AUTO_HOME_VISIT_TAG_NAME).one()
    linked = (
        db.query(person_tags)
        .filter(person_tags.c.person_id == s.id, person_tags.c.tag_id == tag.id)
        .first()
    )
    assert linked is not None


def test_home_visit_mark_done_skips_tag_when_auto_tags_disabled(make_client, db, headers):
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    teacher.payload = validate_person_payload("teacher", {"auto_tags": False})
    s = _seed_person(db, "王小明", "S002")
    db.commit()
    client = make_client(students.router)
    r = client.post(
        f"/api/students/{s.id}/events",
        json={"event_type": "home_visited", "summary": "常规家访"},
        headers=headers,
    )
    ev_id = r.json()["id"]
    r = client.patch(
        f"/api/students/{s.id}/events/{ev_id}",
        json={"event_type": "home_visited", "summary": "常规家访", "done": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert db.query(Tag).filter(Tag.name == AUTO_HOME_VISIT_TAG_NAME).count() == 0


def test_guardian_linking_and_detail(make_client, db, headers):
    s1 = _seed_person(db, "王浩", "S001")
    s2 = _seed_person(db, "邓晓彤", "S002")
    db.commit()
    client = make_client(students.router)

    # 王浩 gets two guardians
    r = client.post(f"/api/students/{s1.id}/guardians",
                    json={"name": "王女士", "phone": "13900000001", "relationship": "母亲"},
                    headers=headers)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/students/{s1.id}/guardians",
                    json={"name": "王秀英", "phone": "13900000000", "relationship": "祖母"},
                    headers=headers)
    assert r.status_code == 201, r.text
    grandmah = r.json()

    # the same phone on another student's guardian merges into one Person
    r = client.post(f"/api/students/{s2.id}/guardians",
                    json={"name": "王秀英", "phone": "13900000000", "relationship": "外祖母"},
                    headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == grandmah["id"]

    # guardian detail: contact info plus both wards with their relationships
    r = client.get(f"/api/guardians/{grandmah['id']}", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "王秀英"
    assert data["phone"] == "13900000000"
    rels = {w["name"]: w["relationship"] for w in data["wards"]}
    assert rels == {"王浩": "祖母", "邓晓彤": "外祖母"}

    # unlink removes one student's link; the guardian Person survives
    r = client.delete(f"/api/students/{s2.id}/guardians/{grandmah['id']}", headers=headers)
    assert r.status_code == 200, r.text
    r = client.get(f"/api/guardians/{grandmah['id']}", headers=headers)
    assert [w["name"] for w in r.json()["wards"]] == ["王浩"]
    r = client.delete(f"/api/students/{s2.id}/guardians/{grandmah['id']}", headers=headers)
    assert r.status_code == 404


def test_create_comment_appears_on_primary_and_mentioned_timelines(make_client, db, headers):
    s1 = _seed_person(db, "林晓雨", "S001")
    s2 = _seed_person(db, "王小明", "S002")
    db.commit()
    client = make_client(students.router)

    r = client.post(
        "/api/comments",
        json={
            "student_id": str(s1.id),
            "notes": "课间与王小明发生争执，已分别谈话。",
            "mentioned_student_ids": [str(s2.id)],
            "occurred_at": "2026-09-02T10:00:00",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    event_id = r.json()["id"]
    ev = db.get(Event, uuid.UUID(event_id))
    assert ev.type == "comment"
    assert ev.title == "课间与王小明发生争执，已分别谈话。"
    assert ev.payload["notes"] == "课间与王小明发生争执，已分别谈话。"
    assert ev.payload["about"] == {"id": str(s1.id), "name": "林晓雨"}
    assert ev.payload["mentioned"] == [{"id": str(s2.id), "name": "王小明"}]
    teacher_id = db.query(Person).filter(Person.phone == "13800000001").one().id
    assert {p.id for p in ev.attendees} == {s1.id, s2.id, teacher_id}

    for sid in (s1.id, s2.id):
        r = client.get(f"/api/students/{sid}/timeline", headers=headers)
        assert r.status_code == 200, r.text
        types = [row["event_type"] for row in r.json()]
        assert "comment" in types


def test_get_comment_infers_primary_without_about(make_client, db, headers):
    s1 = _seed_person(db, "林晓雨", "S001")
    s2 = _seed_person(db, "王小明", "S002")
    db.commit()
    client = make_client(students.router)

    r = client.post(
        "/api/comments",
        json={
            "student_id": str(s1.id),
            "notes": "legacy shape test",
            "mentioned_student_ids": [str(s2.id)],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    event_id = r.json()["id"]
    ev = db.get(Event, uuid.UUID(event_id))
    payload = dict(ev.payload or {})
    payload.pop("about", None)
    ev.payload = payload
    db.commit()

    r = client.get(f"/api/comments/{event_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["student_id"] == str(s1.id)
    assert r.json()["notes"] == "legacy shape test"


def test_calendar_lists_comment_once_for_mentioned_students(client, db, headers):
    s1 = _seed_person(db, "林晓雨", "S001")
    s2 = _seed_person(db, "王小明", "S002")
    cls = _seed_class(db)
    _enroll(db, s1, cls)
    _enroll(db, s2, cls)
    db.commit()
    r = client.post(
        "/api/comments",
        json={
            "student_id": str(s1.id),
            "notes": "提及王小明",
            "mentioned_student_ids": [str(s2.id)],
            "occurred_at": "2026-09-02T10:00:00",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text

    cal = client.get(
        "/api/calendar?year=2026&month=9",
        headers=headers,
    )
    assert cal.status_code == 200, cal.text
    comments = [
        item for item in cal.json()["items"]
        if item.get("event_type") == "comment"
    ]
    assert len(comments) == 1
    assert comments[0]["student_id"] == str(s1.id)


def test_calendar_birthday_appears_once_per_student(make_client, db, headers):
    s = _seed_person(db, "王五", "S005", birth_date="2000-12-20")
    sync_birthday_event(db, s)
    db.commit()
    # Simulate a duplicate row from an older bug.
    birthday = db.query(Event).filter(Event.type == "birthday").one()
    duplicate = Event(
        type="birthday",
        title="生日",
        start_time=datetime(2026, 12, 20, 9, 0),
        payload={"birth_date": "2000-12-20"},
    )
    duplicate.attendees = [s]
    db.add(duplicate)
    db.commit()
    client = make_client(dashboard.router)

    r = client.get("/api/calendar?year=2026&month=12", headers=headers)
    assert r.status_code == 200, r.text
    birthdays = [i for i in r.json()["items"] if i.get("event_type") == "birthday"]
    assert len(birthdays) == 1
    assert birthdays[0]["student_id"] == str(s.id)
    assert birthdays[0]["id"] == str(birthday.id)


def test_update_student_birth_date_keeps_one_birthday_event(make_client, db, headers):
    s = _seed_person(db, "王五", "S005", birth_date="2000-12-20")
    sync_birthday_event(db, s)
    db.commit()
    client = make_client(students.router)

    r = client.patch(
        f"/api/students/{s.id}",
        json={"birth_date": "2001-01-15"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert db.query(Event).filter(Event.type == "birthday").count() == 1
    row = db.query(Event).filter(Event.type == "birthday").one()
    assert row.payload == {"birth_date": "2001-01-15"}


def test_calendar_projects_birthdays_when_enabled(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    sync_birthday_event(db, s)
    db.commit()
    client = make_client(dashboard.router)
    birthday_event = db.query(Event).filter(Event.type == "birthday").one()

    r = client.get("/api/calendar?year=2026&month=5", headers=headers)
    assert r.status_code == 200, r.text
    birthdays = [i for i in r.json()["items"] if i.get("event_type") == "birthday"]
    assert len(birthdays) == 1
    assert birthdays[0]["student_id"] == str(s.id)
    assert birthdays[0]["date"] == "2026-05-14"
    assert birthdays[0]["id"] == str(birthday_event.id)


def test_calendar_hides_birthdays_when_disabled(make_client, db, headers):
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    payload = dict(teacher.payload or {})
    payload["calendar_birthdays"] = False
    teacher.payload = validate_person_payload("teacher", payload)
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    sync_birthday_event(db, s)
    db.commit()
    client = make_client(dashboard.router)

    r = client.get("/api/calendar?year=2026&month=5", headers=headers)
    assert r.status_code == 200, r.text
    assert all(i.get("event_type") != "birthday" for i in r.json()["items"])


def test_deactivate_student_removes_birthday_event(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    sync_birthday_event(db, s)
    db.commit()
    client = make_client(students.router)
    assert db.query(Event).filter(Event.type == "birthday").count() == 1

    r = client.patch(
        f"/api/students/{s.id}",
        json={"status": "inactive"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert db.query(Event).filter(Event.type == "birthday").count() == 0


def test_teachers_me_event_types_returns_manual_list(make_client, db, headers):
    r = make_client(students.router).get("/api/teachers/me/event-types",
                                         headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == sorted(MANUAL_EVENT_TYPES)


# ---------------------------------------------------------------------------
# PATCH /results/{id} — score event payload edits + absent toggle
# ---------------------------------------------------------------------------

def test_patch_result_edits_score_payload_silently(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001")
    ev = _score_event(db, s, "期中考试", "math", score=88.0, max_score=120.0)
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/results/{ev.id}",
                     json={"score": 150.0, "reason": "超出满分"},
                     headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "score out of range"

    r = client.patch(f"/api/results/{ev.id}", json={"score": 92.0}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(ev.id), "score": 92.0, "changed": True}
    db.refresh(ev)
    assert ev.payload["score"] == 92.0

    detail = client.get(f"/api/students/{s.id}", headers=headers)
    assert detail.status_code == 200, detail.text
    math_row = next(row for row in detail.json()["scores"] if row["subject"] == "math")
    assert math_row["score"] == 92.0
    assert "correction" not in math_row  # 更正事件已废除：就地改分不留痕
    assert ev.payload["subject"] == "math"  # merge keeps sibling keys
    assert db.query(Event).filter(Event.type == "result_changed").count() == 0

    # unchanged value short-circuits
    r = client.patch(f"/api/results/{ev.id}", json={"score": 92.0}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(ev.id), "score": 92.0, "changed": False}
    assert db.query(Event).filter(Event.type == "result_changed").count() == 0

    # a non-score event id is not a result
    enrolled = eventing.create_event(db, event_type="enrolled", title="入学",
                                     start_time=datetime(2026, 2, 20),
                                     payload={"class_name": "c"},
                                     attendee_ids=[s.id])
    db.commit()
    r = client.patch(f"/api/results/{enrolled.id}", json={"score": 1.0},
                     headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "result not found"
    r = client.patch(f"/api/results/{uuid.uuid4()}", json={"score": 1.0},
                     headers=headers)
    assert r.status_code == 404


def test_patch_result_absent_toggle_uses_absent_convention(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001")
    ev = _score_event(db, s, "期中考试", "math", score=88.0)
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/results/{ev.id}", json={"score": None}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(ev.id), "score": None, "changed": True}
    db.refresh(ev)
    assert ev.payload["absent"] is True
    assert "score" not in ev.payload

    r = client.patch(f"/api/results/{ev.id}", json={"score": 50.0}, headers=headers)
    assert r.status_code == 200, r.text
    db.refresh(ev)
    assert ev.payload["score"] == 50.0
    assert ev.payload["absent"] is False


# ---------------------------------------------------------------------------
# last_exam mapping — old response keys from score-event sources
# ---------------------------------------------------------------------------

def test_last_exam_summary_maps_from_score_events(make_client, db, headers):
    cls = _seed_class(db)
    s = _seed_person(db, "林晓雨", "S001")
    _enroll(db, s, cls)
    _score_event(db, s, "期中考试", "math", score=90.0)
    _score_event(db, s, "期中考试", "english", absent=True)
    _score_event(db, s, "月考", "math", score=80.0,
                 start=datetime(2026, 4, 1, 9, 0))
    # the exam Event of the latest sitting resolves exam_id (workspace-tagged,
    # same as API-created sittings)
    exam_ev = eventing.create_event(db, event_type="exam", title="期中考试",
                                    start_time=datetime(2026, 5, 20, 9, 0),
                                    payload={"term": "spring",
                                             "workspace_id": ensure_workspace_id(_teacher_of(db))})
    db.commit()
    client = make_client(students.router)

    r = client.get("/api/students", headers=headers)
    last = r.json()[0]["last_exam"]
    assert set(last) == {"exam_id", "exam_name", "exam_date", "scores"}
    assert last["exam_name"] == "期中考试"  # score title prefix before "·"
    assert last["exam_date"] == "2026-05-20"  # latest score event start_time
    assert last["scores"] == {"math": 90.0}  # absent english excluded
    assert last["exam_id"] == str(exam_ev.id)

    # without a matching exam Event (different day), exam_id has no source;
    # last_exam rides on the list response, exactly like the old router
    s2 = _seed_person(db, "王小明", "S002")
    _score_event(db, s2, "期中考试", "math", score=70.0,
                 start=datetime(2026, 6, 5, 9, 0))
    db.commit()
    r = client.get("/api/students", headers=headers)
    row2 = next(row for row in r.json() if row["id"] == str(s2.id))
    assert row2["last_exam"]["exam_id"] is None
    assert row2["last_exam"]["exam_name"] == "期中考试"
    assert row2["last_exam"]["scores"] == {"math": 70.0}
