"""Students: CRUD on Person payloads, tags, and the Event timeline.

Students are Person rows whose payload role is "student" (name, admission_no,
guardian contact… all live in the JSONB payload — see app.payloads). Every
history/timeline item is an Event row linked through person_events; birthdays
are NOT persisted anymore — the timeline projects the next occurrence from
payload["birth_date"] (see student_timeline).

Score "results" are per-student per-subject Events of type "score" whose title
is "<exam name>·<subject>" (the prefix groups a sitting; subject/score/
max_score/absent live in the payload — the locked absent convention is
absent=true with no score key). PATCH /results/{id} edits such an Event.
"""
from datetime import date, datetime, time, timedelta
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import (
    MANUAL_EVENT_TYPES,
    RECORD_EVENT_TYPES,
    SYSTEM_EVENT_TYPES,
    create_event,
    next_birthday_date,
)
from ..models import Class, Enrollment, Event, Person, Tag, person_events, person_tags
from ..models._common import utcnow
from ..payloads import validate_event_payload, validate_person_payload
from ..security import hash_password

router = APIRouter(
    tags=["students"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# display titles for the events this router writes (Event.title is NOT NULL;
# the old StudentEvent rows had no title, so these are new-schema labels)
_RECORD_TITLES = {
    "home_visited": "家访",
    "talk": "谈话",
    "tutoring": "辅导",
    "parent_call": "电话沟通",
    "note_added": "随笔",
    "birthday": "生日",
    "enrolled": "入学",
    "class_moved": "调班",
}

# event types a teacher may create/edit through the generic record endpoints
# (the old "custom event type" feature is gone: event.type has a CHECK
# constraint over the fixed vocabulary, so only the manual set + birthday pass)
_RECORDABLE_TYPES = MANUAL_EVENT_TYPES | {"birthday"}


def _record_title(event_type: str) -> str:
    return _RECORD_TITLES.get(event_type, event_type)


def _record_payload(event_type: str, summary: str, purpose: str | None,
                    follow_up_needed: bool, follow_up_note: str | None,
                    old_payload: dict | None = None) -> dict:
    """Map the old record body onto the per-type payload schemas.

    talk/tutoring/parent_call/note_added carry {"notes"}; home_visited carries
    {"summary","follow_up"} (follow_up needed+note collapse into follow_up);
    a patched-to-birthday event keeps its birth_date.
    """
    if event_type == "home_visited":
        return {
            "summary": summary,
            "follow_up": follow_up_note if follow_up_needed else None,
        }
    if event_type == "birthday":
        return {"birth_date": (old_payload or {}).get("birth_date")}
    return {"notes": summary}


def _score_title(exam_name: str, subject: str) -> str:
    return f"{exam_name}·{subject}"


def _exam_name_of_score(event: Event) -> str:
    # title convention "<exam name>·<subject>" → prefix is the sitting name
    title = event.title or ""
    return title.rsplit("·", 1)[0] if "·" in title else title


def _tags_for_student(db: Session, person_id: uuid.UUID) -> list[dict]:
    rows = (
        db.query(Tag)
        .join(person_tags, person_tags.c.tag_id == Tag.id)
        .filter(person_tags.c.person_id == person_id)
        .order_by(Tag.created_at, Tag.id)
        .all()
    )
    return [{"id": str(tg.id), "name": tg.name, "color": tg.color} for tg in rows]


def _prune_unused_tags(db: Session) -> None:
    used = db.query(person_tags.c.tag_id).distinct()
    db.query(Tag).filter(~Tag.id.in_(used)).delete(synchronize_session=False)


def _find_or_create_tag(db: Session, name: str, color: str) -> Tag:
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag is None:
        tag = Tag(name=name, color=color)
        db.add(tag)
        db.flush()
    return tag


def current_class(db: Session, person_id: uuid.UUID) -> Class | None:
    return (
        db.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.person_id == person_id,
            Enrollment.valid_to.is_(None),
        )
        .first()
    )


def _status_of(person: Person) -> str:
    return "active" if (person.payload or {}).get("is_active", True) else "inactive"


def _score_events(db: Session, person_id: uuid.UUID,
                  order_desc: bool = False) -> list[Event]:
    q = (
        db.query(Event)
        .filter(Event.type == "score", Event.attendees.any(Person.id == person_id))
    )
    if order_desc:
        return q.order_by(Event.start_time.desc(), Event.created_at.desc()).all()
    return q.order_by(Event.start_time, Event.payload["subject"].as_string()).all()


def _exam_event_id(db: Session, exam_name: str, exam_date: str,
                   cache: dict | None = None) -> str | None:
    """The exam Event of a sitting, matched by title + the day falling inside
    its [first_day, last_day] span (str id), or None."""
    if cache is not None and (exam_name, exam_date) in cache:
        return cache[(exam_name, exam_date)]
    day = date.fromisoformat(exam_date)
    row = (
        db.query(Event.id)
        .filter(
            Event.type == "exam",
            Event.title == exam_name,
            Event.start_time <= datetime.combine(day, time.max),
            func.coalesce(Event.end_time, Event.start_time)
            >= datetime.combine(day, time.min),
        )
        .first()
    )
    exam_id = str(row[0]) if row else None
    if cache is not None:
        cache[(exam_name, exam_date)] = exam_id
    return exam_id


def last_exam_summary(db: Session, person_id: uuid.UUID) -> dict | None:
    """The student's most recent graded exam: name + per-subject scores.

    Old response keys, new sources: exam_name ← score-event title prefix
    (everything before "·"), exam_date ← the latest score event's start_time
    date, scores ← payload subject/score of that same sitting (title prefix +
    date), skipping absent entries; exam_id ← the matching type="exam" Event
    of that day, None when no such row exists.
    """
    events = _score_events(db, person_id, order_desc=True)
    latest = next(
        (e for e in events
         if not (e.payload or {}).get("absent") and (e.payload or {}).get("score") is not None),
        None,
    )
    if latest is None:
        return None
    exam_name = _exam_name_of_score(latest)
    exam_date = latest.start_time.date().isoformat()
    scores: dict = {}
    for e in events:
        pl = e.payload or {}
        if _exam_name_of_score(e) != exam_name or e.start_time.date().isoformat() != exam_date:
            continue
        if pl.get("absent") or pl.get("score") is None:
            continue
        scores[pl.get("subject")] = pl.get("score")
    return {
        "exam_id": _exam_event_id(db, exam_name, exam_date),
        "exam_name": exam_name,
        "exam_date": exam_date,
        "scores": scores,
    }


@router.get("/students")
def list_students(db: Session = Depends(get_db)):
    students = (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "student")
        .order_by(Person.payload["admission_no"].as_string())
        .all()
    )
    out = []
    for s in students:
        cls = current_class(db, s.id)
        out.append(
            {
                "id": str(s.id),
                "admission_no": (s.payload or {}).get("admission_no"),
                "name": (s.payload or {}).get("name"),
                "gender": (s.payload or {}).get("gender"),
                "status": _status_of(s),
                "class": {"id": str(cls.id), "name": cls.name} if cls else None,
                "last_exam": last_exam_summary(db, s.id),
                "tags": _tags_for_student(db, s.id),
            }
        )
    return out


@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    """All in-use tags (attached to at least one person)."""
    tags = (
        db.query(Tag, func.count(person_tags.c.person_id))
        .outerjoin(person_tags, person_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .having(func.count(person_tags.c.person_id) > 0)
        .order_by(func.count(person_tags.c.person_id).desc(), Tag.name)
        .all()
    )
    return [
        {"id": str(tag.id), "name": tag.name, "color": tag.color, "usage": count}
        for tag, count in tags
    ]


class StudentTagIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str


@router.post("/students/{student_id}/tags", status_code=201)
def attach_tag(
    student_id: uuid.UUID,
    body: StudentTagIn,
    db: Session = Depends(get_db),
):
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="tag name is required")
    if not COLOR_RE.match(body.color):
        raise HTTPException(status_code=400, detail="颜色格式不正确")
    tag = _find_or_create_tag(db, name, body.color.lower())
    if (
        db.query(person_tags)
        .filter(person_tags.c.person_id == person.id, person_tags.c.tag_id == tag.id)
        .first()
        is not None
    ):
        raise HTTPException(status_code=409, detail="该标签已添加")
    db.execute(person_tags.insert().values(person_id=person.id, tag_id=tag.id))
    db.commit()
    return {"id": str(tag.id), "name": tag.name, "color": tag.color}


@router.delete("/students/{student_id}/tags/{tag_id}", status_code=204)
def detach_tag(
    student_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    result = db.execute(
        person_tags.delete().where(
            person_tags.c.person_id == student_id, person_tags.c.tag_id == tag_id
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="tag not attached")
    _prune_unused_tags(db)
    db.commit()


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    gender: str | None = None
    birth_date: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    class_id: uuid.UUID


@router.post("/students", status_code=201)
def create_student(
    body: StudentIn,
    db: Session = Depends(get_db),
):
    cls = db.get(Class, body.class_id)
    if cls is None:
        raise HTTPException(status_code=400, detail="class not found")
    max_no = 0
    admission_nos = (
        db.query(Person.payload["admission_no"].as_string())
        .filter(Person.payload["role"].as_string() == "student")
        .all()
    )
    for (no,) in admission_nos:
        digits = "".join(ch for ch in no if ch.isdigit())
        if digits.isdigit():
            max_no = max(max_no, int(digits))
    admission_no = f"S{max_no + 1}"
    payload = validate_person_payload(
        "student",
        {
            "name": body.name.strip(),
            "admission_no": admission_no,
            "gender": body.gender or None,
            "birth_date": body.birth_date.isoformat() if body.birth_date else None,
            "guardian_name": body.guardian_name or None,
            "guardian_phone": body.guardian_phone.strip() if body.guardian_phone else None,
            "address": body.address or None,
        },
    )
    person = Person(password_hash=hash_password(uuid.uuid4().hex), payload=payload)
    db.add(person)
    db.flush()
    db.add(Enrollment(person_id=person.id, class_id=cls.id,
                      valid_from=date.today(), reason="admitted"))
    create_event(db, event_type="enrolled", title="入学", start_time=utcnow(),
                 payload={"class_name": cls.name}, attendee_ids=[person.id])
    # no persisted birthday event: the timeline projects it from birth_date
    db.commit()
    return {"id": str(person.id), "admission_no": admission_no, "name": payload["name"]}


@router.get("/students/{student_id}")
def get_student(student_id: uuid.UUID, db: Session = Depends(get_db)):
    s = db.get(Person, student_id)
    if s is None or s.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    cls = current_class(db, s.id)
    exam_id_cache: dict = {}
    scores = []
    for r in _score_events(db, s.id):
        pl = r.payload or {}
        exam_name = _exam_name_of_score(r)
        exam_date = r.start_time.date().isoformat()
        scores.append(
            {
                "result_id": str(r.id),
                "exam_id": _exam_event_id(db, exam_name, exam_date, exam_id_cache),
                "exam_name": exam_name,
                "exam_date": exam_date,
                "subject": pl.get("subject"),
                "score": pl.get("score"),
                "full_score": pl.get("max_score"),
                "status": "absent" if pl.get("absent") else "entered",
            }
        )
    return {
        "id": str(s.id),
        "admission_no": (s.payload or {}).get("admission_no"),
        "name": (s.payload or {}).get("name"),
        "gender": (s.payload or {}).get("gender"),
        "birth_date": (s.payload or {}).get("birth_date"),
        "guardian_name": (s.payload or {}).get("guardian_name"),
        "guardian_phone": (s.payload or {}).get("guardian_phone"),
        "address": (s.payload or {}).get("address"),
        "status": _status_of(s),
        "class": {"id": str(cls.id), "name": cls.name} if cls else None,
        "scores": scores,
        "tags": _tags_for_student(db, s.id),
    }


@router.get("/students/{student_id}/timeline")
def student_timeline(student_id: uuid.UUID, db: Session = Depends(get_db)):
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(Event)
        .filter(Event.attendees.any(Person.id == student_id))
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .all()
    )
    out = [_event_to_dict(e) for e in rows]
    # projected birthday: identical shape to a serialized birthday event,
    # dated the next occurrence, never persisted (old rows were recurring
    # StudentEvents; the payload's birth_date is the single source now)
    birth_date = (person.payload or {}).get("birth_date")
    if birth_date:
        bday = next_birthday_date(date.fromisoformat(birth_date))
        out.append(
            {
                "id": f"birthday-{person.id}",
                "event_type": "birthday",
                "occurred_at": datetime.combine(bday, time(9, 0)).isoformat(),
                "actor": None,
                "payload": {"birth_date": birth_date},
                "actor_teacher_id": None,
                "is_system": False,
            }
        )
    return out


class EventRecordIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=2000)
    purpose: str | None = None
    follow_up_needed: bool = False
    follow_up_note: str | None = None
    occurred_at: datetime | None = None


@router.post("/students/{student_id}/events", status_code=201)
def create_event_record(
    student_id: uuid.UUID,
    body: EventRecordIn,
    db: Session = Depends(get_db),
):
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    if body.event_type not in _RECORDABLE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的事件类型")
    event = create_event(
        db,
        event_type=body.event_type,
        title=_record_title(body.event_type),
        start_time=body.occurred_at or utcnow(),
        payload=_record_payload(body.event_type, body.summary, body.purpose,
                                body.follow_up_needed, body.follow_up_note),
        attendee_ids=[person.id],
    )
    db.commit()
    return {"id": str(event.id), "status": "created"}


@router.get("/students/{student_id}/events")
def list_student_events(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    if db.get(Person, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(Event)
        .filter(
            Event.attendees.any(Person.id == student_id),
            Event.type.notin_(list(SYSTEM_EVENT_TYPES)),
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(e.id),
            "event_type": e.type,
            "occurred_at": e.start_time.isoformat(),
            "actor": None,
            "payload": e.payload or {},
        }
        for e in rows
    ]


@router.get("/records")
def list_records(
    db: Session = Depends(get_db),
):
    """所有事件: every Event school-wide (records are just a subset), newest first."""
    rows = (
        db.query(Event, Person)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": str(ev.id),
            "student_id": str(person.id),
            "student_name": (person.payload or {}).get("name"),
            "event_type": ev.type,
            "occurred_at": ev.start_time.isoformat(),
            "actor": None,
            "payload": ev.payload or {},
        }
        for ev, person in rows
    ]


@router.get("/teachers/me/event-types")
def my_event_types(db: Session = Depends(get_db)):
    """The manual record types (the old recently-used-custom-types list died
    with free-form event types — the event table now CHECK-constrains type)."""
    return sorted(MANUAL_EVENT_TYPES)


def _event_to_dict(e: Event) -> dict:
    # Event has no actor column in the new schema, so actor/actor_teacher_id
    # are always None (keys kept for API-shape stability)
    return {
        "id": str(e.id),
        "event_type": e.type,
        "occurred_at": e.start_time.isoformat(),
        "actor": None,
        "payload": e.payload or {},
        "actor_teacher_id": None,
        "is_system": e.type in SYSTEM_EVENT_TYPES,
    }


@router.get("/students/{student_id}/events/{event_id}")
def get_event(
    student_id: uuid.UUID,
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    e = db.get(Event, event_id)
    if (
        e is None
        or db.query(person_events)
        .filter(person_events.c.event_id == e.id,
                person_events.c.person_id == student_id)
        .first()
        is None
    ):
        raise HTTPException(status_code=404, detail="event not found")
    return _event_to_dict(e)


@router.patch("/students/{student_id}/events/{event_id}")
def update_event(
    student_id: uuid.UUID,
    event_id: uuid.UUID,
    body: EventRecordIn,
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if (
        ev is None
        or db.query(person_events)
        .filter(person_events.c.event_id == ev.id,
                person_events.c.person_id == student_id)
        .first()
        is None
    ):
        raise HTTPException(status_code=404, detail="event not found")
    if ev.type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be modified")
    if body.event_type not in _RECORDABLE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的事件类型")
    old_payload = ev.payload or {}
    ev.type = body.event_type
    ev.title = _record_title(body.event_type)
    ev.start_time = body.occurred_at or ev.start_time
    # copy-modify-reassign: JSON columns don't see in-place mutation
    ev.payload = _record_payload(body.event_type, body.summary, body.purpose,
                                 body.follow_up_needed, body.follow_up_note,
                                 old_payload)
    db.commit()
    db.refresh(ev)
    return {"id": str(ev.id), "status": "updated"}


@router.delete("/students/{student_id}/events/{event_id}")
def delete_event(
    student_id: uuid.UUID,
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if (
        ev is None
        or db.query(person_events)
        .filter(person_events.c.event_id == ev.id,
                person_events.c.person_id == student_id)
        .first()
        is None
    ):
        raise HTTPException(status_code=404, detail="event not found")
    if ev.type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be deleted")
    db.delete(ev)
    db.commit()
    return {"status": "deleted"}


class ScoreUpdateIn(BaseModel):
    score: float | None = None  # None marks the absence (absent=true, no score key)
    reason: str | None = None


@router.patch("/results/{result_id}")
def update_result(
    result_id: uuid.UUID,
    body: ScoreUpdateIn,
    db: Session = Depends(get_db),
):
    ev = db.get(Event, result_id)
    if ev is None or ev.type != "score":
        raise HTTPException(status_code=404, detail="result not found")
    payload = dict(ev.payload or {})
    max_score = payload.get("max_score")
    if body.score is not None and (body.score < 0 or max_score is None or body.score > max_score):
        raise HTTPException(status_code=400, detail="score out of range")
    old = payload.get("score")
    if body.score is not None and old is not None and abs(body.score - old) < 0.01:
        return {"id": str(ev.id), "score": old, "changed": False}

    new_score: float | None
    if body.score is None:
        # absent convention: absent=true and no score key
        payload.pop("score", None)
        payload["absent"] = True
        new_score = None
    else:
        payload["score"] = body.score
        payload["absent"] = False
        new_score = body.score
    ev.payload = validate_event_payload("score", payload)  # validated + fresh dict
    attendee = ev.attendees[0] if ev.attendees else None
    create_event(
        db,
        event_type="result_changed",
        title=f"{payload.get('subject')}成绩更正",
        start_time=utcnow(),
        payload={
            "exam": _exam_name_of_score(ev),
            "subject": payload.get("subject"),
            "old": old,
            "new": new_score,
            "reason": body.reason,
        },
        attendee_ids=[attendee.id] if attendee else (),
    )
    db.commit()
    return {"id": str(ev.id), "score": new_score, "changed": True}


class StudentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: str | None = None
    birth_date: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = Field(default=None, min_length=5, max_length=40)
    address: str | None = None
    status: str | None = None  # active | inactive
    class_id: uuid.UUID | None = None  # omit to leave class unchanged


@router.patch("/students/{student_id}")
def update_student(
    student_id: uuid.UUID,
    body: StudentUpdateIn,
    db: Session = Depends(get_db),
):
    s = db.get(Person, student_id)
    if s is None or s.role != "student":
        raise HTTPException(status_code=404, detail="student not found")

    # copy-modify-reassign so a partial patch never drops sibling payload keys
    payload = dict(s.payload or {})
    if body.name is not None:
        payload["name"] = body.name.strip()
    if body.gender is not None:
        payload["gender"] = body.gender or None
    if body.birth_date is not None:
        payload["birth_date"] = body.birth_date.isoformat()
    if body.guardian_name is not None:
        payload["guardian_name"] = body.guardian_name or None
    if body.guardian_phone is not None:
        payload["guardian_phone"] = body.guardian_phone.strip()
    if body.address is not None:
        payload["address"] = body.address or None
    if body.status is not None:
        if body.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")
        payload["is_active"] = body.status == "active"
    s.payload = validate_person_payload("student", payload)

    # Class change: close current enrollment, open a new one, record event.
    if body.class_id is not None:
        new_cls = db.get(Class, body.class_id)
        if new_cls is None:
            raise HTTPException(status_code=400, detail="class not found")
        current = current_class(db, s.id)
        if current is None or current.id != body.class_id:
            old_enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.person_id == student_id, Enrollment.valid_to.is_(None))
                .first()
            )
            old_name = current.name if current else None
            if old_enrollment is not None:
                old_enrollment.valid_to = date.today()
            db.add(
                Enrollment(
                    person_id=student_id,
                    class_id=new_cls.id,
                    valid_from=date.today(),
                    reason="moved",
                )
            )
            if old_name is not None:
                create_event(
                    db,
                    event_type="class_moved",
                    title="调班",
                    start_time=utcnow(),
                    payload={"from_class": old_name, "to_class": new_cls.name},
                    attendee_ids=[s.id],
                )

    db.commit()
    cls = current_class(db, s.id)
    return {
        "id": str(s.id),
        "admission_no": (s.payload or {}).get("admission_no"),
        "name": (s.payload or {}).get("name"),
        "gender": (s.payload or {}).get("gender"),
        "status": _status_of(s),
        "class": {"id": str(cls.id), "name": cls.name} if cls else None,
    }


@router.delete("/students/{student_id}")
def delete_student(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    s = db.get(Person, student_id)
    if s is None or s.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    # Only allow hard delete when the student has no written evidence so the
    # data integrity stays intact. Otherwise move to inactive.
    # Remaining evidence: score Events and any teacher-written record (the
    # generic 跟进记录 — home visits, talks, calls, tutoring, notes).
    has_results = (
        db.query(Event)
        .filter(Event.type == "score", Event.attendees.any(Person.id == student_id))
        .first()
        is not None
    )
    has_records = (
        db.query(Event)
        .filter(Event.type.in_(list(MANUAL_EVENT_TYPES)),
                Event.attendees.any(Person.id == student_id))
        .first()
        is not None
    )
    if has_results or has_records:
        # Soft delete: is_active=false + close enrollments (copy-modify-reassign)
        payload = dict(s.payload or {})
        payload["is_active"] = False
        s.payload = validate_person_payload("student", payload)
        for e in (
            db.query(Enrollment)
            .filter(Enrollment.person_id == student_id, Enrollment.valid_to.is_(None))
            .all()
        ):
            e.valid_to = date.today()
        create_event(db, event_type="note_added", title="随笔", start_time=utcnow(),
                     payload={"notes": "账号停用"}, attendee_ids=[s.id])
        db.commit()
        return {"ok": True, "action": "deactivated"}

    event_ids = [
        row[0]
        for row in db.query(person_events.c.event_id)
        .filter(person_events.c.person_id == student_id)
        .all()
    ]
    if event_ids:
        db.query(Event).filter(Event.id.in_(event_ids)).delete(synchronize_session=False)
    db.execute(person_tags.delete().where(person_tags.c.person_id == student_id))
    db.query(Enrollment).filter(Enrollment.person_id == student_id).delete(
        synchronize_session=False
    )
    db.delete(s)
    db.commit()
    return {"ok": True, "action": "deleted"}
