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
from app.eventing import MANUAL_EVENT_TYPES, next_birthday_date
from app.models import AuthSession, Class, Enrollment, Event, Person, Tag
from app.payloads import validate_person_payload
from app.routers import students
from app.security import hash_password


# ---------------------------------------------------------------------------
# Seed helpers — persons / classes / enrollments / events, straight on the db
# ---------------------------------------------------------------------------

def _seed_person(db, name: str, admission_no: str, *, birth_date: str | None = None,
                 active: bool = True) -> Person:
    payload = validate_person_payload("student", {"name": name, "admission_no": admission_no})
    if birth_date:
        payload["birth_date"] = birth_date
    if not active:
        payload["is_active"] = False
    p = Person(password_hash=hash_password(uuid.uuid4().hex), payload=payload)
    db.add(p)
    db.flush()
    return p


def _seed_teacher(db, phone: str = "13800000001") -> Person:
    p = Person(phone=phone, password_hash=hash_password("123456"),
               payload=validate_person_payload("teacher", {"name": "王老师"}))
    db.add(p)
    db.flush()
    return p


def _headers(db, person: Person, token: str = "t" * 64) -> dict:
    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def _seed_class(db, name: str = "七年级1班") -> Class:
    c = Class(name=name, grade_level=7, academic_year="2026")
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
                  start: datetime) -> Event:
    payload = ({"summary": summary} if event_type == "home_visited"
               else {"notes": summary})
    ev = eventing.create_event(db, event_type=event_type, title=summary,
                               start_time=start, payload=payload,
                               attendee_ids=[person.id])
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
                            "class", "last_exam", "tags"}
    assert rows[0]["name"] == "张一"
    assert rows[0]["status"] == "active"
    assert rows[0]["class"] == {"id": str(cls.id), "name": cls.name}
    assert rows[0]["last_exam"] is None
    assert rows[0]["tags"] == []
    uuid.UUID(rows[0]["id"])


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
    assert person.payload["name"] == "林新"
    assert person.payload["birth_date"] == "2013-06-01"
    assert person.payload["is_active"] is True

    enrollments = db.query(Enrollment).filter(Enrollment.person_id == person.id).all()
    assert len(enrollments) == 1 and enrollments[0].class_id == cls.id
    assert enrollments[0].valid_to is None

    # enrolled event recorded; birthday is projected from the payload at read
    # time — no persisted birthday Event row
    events = db.query(Event).filter(Event.attendees.any(Person.id == person.id)).all()
    assert [e.type for e in events] == ["enrolled"]
    assert events[0].payload == {"class_name": cls.name}


def test_create_student_class_not_found_400(make_client, db, headers):
    r = make_client(students.router).post(
        "/api/students",
        json={"name": " nobody", "class_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "class not found"


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
                         "guardian_name", "guardian_phone", "address", "status",
                         "class", "scores", "tags"}
    assert body["birth_date"] == "2012-05-14"
    assert body["class"] == {"id": str(cls.id), "name": cls.name}
    # ordered by (start_time, subject): 月考 math, 期中 english, 期中 math
    assert [(row["exam_name"], row["subject"]) for row in body["scores"]] == [
        ("月考", "math"), ("期中考试", "english"), ("期中考试", "math")]
    row = body["scores"][2]
    assert set(row) == {"result_id", "exam_id", "exam_name", "exam_date",
                        "subject", "score", "full_score", "status"}
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
    s = _seed_person(db, "林晓雨", "S001")
    payload = dict(s.payload or {})
    payload["guardian_name"] = "林爸爸"
    payload["guardian_phone"] = "13810001000"
    s.payload = payload  # reassign: JSON columns don't see in-place mutation
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/students/{s.id}", json={"address": "幸福路1号"},
                     headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"id", "admission_no", "name", "gender", "status", "class"}
    db.refresh(s)
    assert s.payload["address"] == "幸福路1号"
    # partial patch must not drop sibling payload keys
    assert s.payload["guardian_name"] == "林爸爸"
    assert s.payload["admission_no"] == "S001"
    assert s.payload["name"] == "林晓雨"

    r = client.patch(f"/api/students/{uuid.UUID(int=1)}", json={"address": "x"},
                     headers=headers)
    assert r.status_code == 404


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
    notes = (db.query(Event).filter(Event.type == "note_added",
                                    Event.attendees.any(Person.id == s.id)).all())
    assert [e.payload for e in notes] == [{"notes": "账号停用"}]
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

TIMELINE_KEYS = {"id", "event_type", "occurred_at", "actor", "payload",
                 "actor_teacher_id", "is_system"}


def test_timeline_lists_manual_events_and_projected_birthday(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001", birth_date="2012-05-14")
    _manual_event(db, s, "home_visited", "开学前家访", datetime(2026, 3, 15, 19, 0))
    _manual_event(db, s, "talk", "聊了作业习惯", datetime(2026, 4, 1, 12, 0))
    db.commit()
    client = make_client(students.router)

    r = client.get(f"/api/students/{s.id}/timeline", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()
    assert [it["event_type"] for it in items] == ["talk", "home_visited", "birthday"]
    for it in items:
        assert set(it) == TIMELINE_KEYS

    talk = items[0]
    assert talk["payload"] == {"notes": "聊了作业习惯"}
    assert talk["is_system"] is False

    # the projected birthday: shaped like a serialized event, next occurrence,
    # 09:00 like the old persisted row — and NOT backed by an Event row
    bday = items[-1]
    expected = next_birthday_date(date(2012, 5, 14))
    assert bday["occurred_at"] == datetime.combine(expected, datetime.min.time().replace(hour=9)).isoformat()
    assert bday["payload"] == {"birth_date": "2012-05-14"}
    assert bday["is_system"] is False
    assert db.query(Event).filter(Event.type == "birthday").count() == 0

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
                    json={"event_type": "talk", "summary": "聊了作业习惯",
                          "occurred_at": "2026-04-01T12:00:00"},
                    headers=headers)
    assert r.status_code == 201, r.text
    created = r.json()
    assert set(created) == {"id", "status"}
    assert created["status"] == "created"
    ev = db.get(Event, uuid.UUID(created["id"]))
    assert ev.type == "talk" and ev.payload == {"notes": "聊了作业习惯"}

    # home visit maps summary/follow_up_note onto the home_visited payload
    r = client.post(f"/api/students/{s.id}/events",
                    json={"event_type": "home_visited", "summary": "开学前家访",
                          "follow_up_needed": True,
                          "follow_up_note": "两周后回访阅读落实情况"},
                    headers=headers)
    assert r.status_code == 201, r.text
    visit = db.get(Event, uuid.UUID(r.json()["id"]))
    assert visit.payload == {"summary": "开学前家访",
                             "follow_up": "两周后回访阅读落实情况"}

    r = client.get(f"/api/students/{s.id}/events", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["event_type"] for row in rows] == ["home_visited", "talk"]
    assert set(rows[0]) == {"id", "event_type", "occurred_at", "actor", "payload"}
    # the enrolled (system) event never shows in the manual-record list
    assert all(row["event_type"] != "enrolled" for row in rows)

    r = client.get(f"/api/students/{s.id}/events/{created['id']}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["event_type"] == "talk"

    r = client.patch(f"/api/students/{s.id}/events/{created['id']}",
                     json={"event_type": "talk", "summary": "改：聊了阅读习惯",
                           "occurred_at": "2026-04-02T12:00:00"},
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": created["id"], "status": "updated"}
    db.refresh(ev)
    assert ev.payload == {"notes": "改：聊了阅读习惯"}
    assert ev.start_time == datetime(2026, 4, 2, 12, 0)

    # system events stay read-only
    enrolled_id = db.query(Event).filter(Event.type == "enrolled").one().id
    r = client.patch(f"/api/students/{s.id}/events/{enrolled_id}",
                     json={"event_type": "talk", "summary": "x"}, headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "system events cannot be modified"
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

def test_records_lists_events_the_teacher_attends(make_client, db, headers):
    teacher = db.query(Person).filter(Person.phone == "13800000001").one()
    s1 = Person(password_hash=hash_password(uuid.uuid4().hex),
                payload=validate_person_payload("student", {
                    "name": "林晓雨", "admission_no": "S001",
                    "guardian_name": "林女士"}))
    db.add(s1)
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
    r = client.post(f"/api/students/{s2.id}/events",
                    json={"event_type": "note_added", "summary": "作业潦草",
                          "occurred_at": "2026-03-20T09:00:00"},
                    headers=headers)
    assert r.status_code == 201, r.text

    _score_event(db, s1, "期中考试", "math", score=90.0)  # student-only, not hers
    other = _seed_teacher(db, phone="13800000002")
    other_headers = _headers(db, other, token="o" * 64)
    r = make_client(students.router).post(
        f"/api/students/{s2.id}/events",
        json={"event_type": "talk", "summary": "另一位老师的谈话",
              "occurred_at": "2026-03-21T10:00:00"},
        headers=other_headers)
    assert r.status_code == 201, r.text
    db.commit()

    r = client.get("/api/records", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    # only the signed-in teacher's own events, newest first
    assert [(row["event_type"], row["student_name"]) for row in rows] == [
        ("note_added", "王小明"), ("home_visited", "林晓雨")]
    assert set(rows[0]) == {"id", "title", "student_id", "student_name",
                            "event_type", "occurred_at", "actor", "payload"}
    assert rows[0]["student_id"] == str(s2.id)
    assert rows[0]["title"] == "随笔"
    assert rows[0]["payload"] == {"notes": "作业潦草"}
    visit = rows[1]
    assert visit["title"] == "家访"
    assert visit["payload"] == {"summary": "开学前家访", "guardian": "林女士"}
    # the type param narrows the feed (the 家访 page reads home_visited only)
    r = client.get("/api/records?type=home_visited", headers=headers)
    assert [(row["event_type"], row["student_name"]) for row in r.json()] == [
        ("home_visited", "林晓雨")]
    # both records carry the teacher as an attendee alongside the student
    for row in rows:
        ev = db.get(Event, uuid.UUID(row["id"]))
        assert {p.id for p in ev.attendees} == {s2.id if row is rows[0] else s1.id,
                                                teacher.id}


def test_teachers_me_event_types_returns_manual_list(make_client, db, headers):
    r = make_client(students.router).get("/api/teachers/me/event-types",
                                         headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == sorted(MANUAL_EVENT_TYPES)


# ---------------------------------------------------------------------------
# PATCH /results/{id} — score event payload edits + absent toggle
# ---------------------------------------------------------------------------

def test_patch_result_edits_score_payload_and_records_change(make_client, db, headers):
    s = _seed_person(db, "林晓雨", "S001")
    ev = _score_event(db, s, "期中考试", "math", score=88.0, max_score=120.0)
    db.commit()
    client = make_client(students.router)

    r = client.patch(f"/api/results/{ev.id}",
                     json={"score": 150.0, "reason": "超出满分"},
                     headers=headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "score out of range"

    r = client.patch(f"/api/results/{ev.id}",
                     json={"score": 92.0, "reason": "改错一道大题"},
                     headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(ev.id), "score": 92.0, "changed": True}
    db.refresh(ev)
    assert ev.payload["score"] == 92.0
    assert ev.payload["subject"] == "math"  # merge keeps sibling keys
    changes = db.query(Event).filter(Event.type == "result_changed").all()
    assert len(changes) == 1
    assert changes[0].payload["old"] == 88.0
    assert changes[0].payload["new"] == 92.0
    assert changes[0].payload["reason"] == "改错一道大题"

    # unchanged value short-circuits
    r = client.patch(f"/api/results/{ev.id}", json={"score": 92.0}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": str(ev.id), "score": 92.0, "changed": False}
    assert db.query(Event).filter(Event.type == "result_changed").count() == 1

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
    # the exam Event of the latest sitting resolves exam_id
    exam_ev = eventing.create_event(db, event_type="exam", title="期中考试",
                                    start_time=datetime(2026, 5, 20, 9, 0),
                                    payload={"term": "spring"})
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
