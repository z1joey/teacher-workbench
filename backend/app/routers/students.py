"""Students: CRUD on Person payloads, tags, and the Event timeline.

Students are Person rows whose payload role is "student"; `name` is a typed
column and the per-student attributes (admission_no, gender, birth_date,
address) live in the JSONB payload — see app.models.payloads. A student's
guardians are Person rows of role "guardian" linked through student_guardians
(no flattened guardian_name/phone on the student anymore). Every
history/timeline item is an Event row linked through person_events. Each active
student with a birth_date gets one system-managed birthday Event (yearly, removed
when the student becomes inactive).

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
    SYSTEM_EVENT_TYPES,
    create_event,
    next_birthday_date,
    sync_birthday_event,
)
from ..models import (
    Class,
    Enrollment,
    Event,
    Person,
    Tag,
    person_events,
    person_tags,
    student_guardians,
)
from ..models._common import utcnow
from ..payloads import validate_event_payload, validate_person_payload
from ..security import hash_password
from ..unassigned import class_for_api, ensure_unassigned_class, is_unassigned_class
from ..workspace import (
    require_class_in_workspace,
    require_student_in_workspace,
    students_query,
    tag_student_workspace,
)

router = APIRouter(
    tags=["students"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
AUTO_HOME_VISIT_TAG_NAME = "已家访"
AUTO_HOME_VISIT_TAG_COLOR = "#2f7d4f"
DEFAULT_HOME_VISIT_PURPOSE = "例行家访"

# display titles for the events this router writes (Event.title is NOT NULL;
# the old StudentEvent rows had no title, so these are new-schema labels)
_RECORD_TITLES = {
    "home_visited": "家访",
    "talk": "谈话",
    "tutoring": "辅导",
    "parent_call": "电话沟通",
    "note_added": "随笔",
    "comment": "评语",
    "birthday": "生日",
    "enrolled": "入学",
    "class_moved": "转班",
}

# event types a teacher may create/edit through the generic record endpoints
_RECORDABLE_TYPES = MANUAL_EVENT_TYPES


def _record_title(event_type: str) -> str:
    return _RECORD_TITLES.get(event_type, event_type)


def _record_payload(event_type: str, summary: str, purpose: str | None,
                    old_payload: dict | None = None,
                    *, done: bool | None = None) -> dict:
    """Map the record body onto the per-type payload schemas.

    talk/tutoring/parent_call/note_added carry {"notes"}; home_visited carries
    {"summary","purpose","done"}; a patched-to-birthday event keeps birth_date.
    """
    if event_type == "home_visited":
        old = old_payload or {}
        purpose_text = (
            (purpose or "").strip()
            or old.get("purpose")
            or DEFAULT_HOME_VISIT_PURPOSE
        )
        out: dict = {
            "purpose": purpose_text,
            "summary": summary.strip() or None,
        }
        if old.get("guardian"):
            out["guardian"] = old["guardian"]
        if done is True:
            out["done"] = True
        elif done is False:
            pass
        elif old.get("done"):
            out["done"] = True
        return out
    if event_type == "birthday":
        return {"birth_date": (old_payload or {}).get("birth_date")}
    if event_type == "comment":
        out = {"notes": summary}
        if old_payload:
            if old_payload.get("mentioned"):
                out["mentioned"] = old_payload["mentioned"]
            if old_payload.get("about"):
                out["about"] = old_payload["about"]
        return out
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


def _teacher_auto_tags_enabled(teacher: Person) -> bool:
    return (teacher.payload or {}).get("auto_tags", True)


def _attach_tag_if_missing(db: Session, student_id: uuid.UUID, name: str, color: str) -> None:
    tag = _find_or_create_tag(db, name, color)
    exists = (
        db.query(person_tags)
        .filter(person_tags.c.person_id == student_id, person_tags.c.tag_id == tag.id)
        .first()
    )
    if exists is None:
        db.execute(person_tags.insert().values(person_id=student_id, tag_id=tag.id))


def _maybe_apply_home_visit_tag(db: Session, student_id: uuid.UUID, teacher: Person) -> None:
    if not _teacher_auto_tags_enabled(teacher):
        return
    _attach_tag_if_missing(
        db, student_id, AUTO_HOME_VISIT_TAG_NAME, AUTO_HOME_VISIT_TAG_COLOR
    )


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


def _admission_no_in_use(
    db: Session, admission_no: str, *, exclude_id: uuid.UUID | None = None,
) -> bool:
    q = db.query(Person.id).filter(
        Person.payload["role"].as_string() == "student",
        Person.payload["admission_no"].as_string() == admission_no,
    )
    if exclude_id is not None:
        q = q.filter(Person.id != exclude_id)
    return q.first() is not None


def _guardians_of(db: Session, student_id: uuid.UUID):
    """The guardian Persons of a student (with the link's relationship),
    ordered by creation."""
    return (
        db.query(Person, student_guardians.c.relationship)
        .join(student_guardians, student_guardians.c.guardian_id == Person.id)
        .filter(student_guardians.c.student_id == student_id)
        .order_by(Person.created_at)
        .all()
    )


def _find_or_create_guardian(db: Session, name: str, phone: str | None,
                             address: str | None = None) -> Person:
    """Locate an existing guardian by phone (or name), else mint a new Person
    of role "guardian". Guardians are independent of the student's lifecycle,
    so two students sharing a phone share one guardian row."""
    name = name.strip()
    phone = (phone or "").strip() or None
    address = (address or "").strip() or None
    guardian = (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "guardian", Person.phone == phone)
        .first()
        if phone
        else None
    )
    if guardian is None:
        guardian = (
            db.query(Person)
            .filter(Person.payload["role"].as_string() == "guardian", Person.name == name)
            .first()
        )
    if guardian is not None:
        if name:
            guardian.name = name
        if phone:
            guardian.phone = phone
        payload = dict(guardian.payload or {})
        if phone:
            payload["phone"] = phone
        if address:
            payload["address"] = address
        guardian.payload = validate_person_payload("guardian", payload)
        return guardian
    guardian = Person(
        name=name,
        phone=phone,
        password_hash=hash_password(uuid.uuid4().hex),
        payload=validate_person_payload("guardian", {"phone": phone, "address": address}),
    )
    db.add(guardian)
    db.flush()
    return guardian


def _set_primary_guardian(db: Session, student_id: uuid.UUID,
                          name: str | None, phone: str | None) -> None:
    """Upsert the student's primary guardian (the single one the form edits):
    merge a matching guardian Person if it exists and link it, dropping the
    school's previous primary link when the name/phone is cleared."""
    existing = _guardians_of(db, student_id)
    if not name and not phone:
        # no guardian supplied — leave the current links untouched
        return
    guardian = _find_or_create_guardian(db, name or "", phone)
    linked_ids = {g.id for g, _ in existing}
    if guardian.id in linked_ids:
        return
    # promote the chosen guardian: drop any other primary links, then add it
    db.execute(student_guardians.delete().where(student_guardians.c.student_id == student_id))
    db.execute(
        student_guardians.insert().values(student_id=student_id, guardian_id=guardian.id)
    )


class GuardianLinkIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=40)
    relationship: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=200)


def _guardian_link(db: Session, student_id: uuid.UUID, guardian: Person,
                   relationship: str | None) -> None:
    """Link a guardian to a student (no-op when already linked); a supplied
    relationship label refreshes the link's."""
    linked = {g.id for g, _ in _guardians_of(db, student_id)}
    if guardian.id in linked:
        if relationship:
            db.execute(
                student_guardians.update()
                .where(student_guardians.c.student_id == student_id,
                       student_guardians.c.guardian_id == guardian.id)
                .values(relationship=relationship)
            )
        return
    db.execute(student_guardians.insert().values(
        student_id=student_id, guardian_id=guardian.id,
        relationship=relationship,
    ))


@router.post("/students/{student_id}/guardians", status_code=201)
def add_student_guardian(
    student_id: uuid.UUID,
    body: GuardianLinkIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Link another guardian to the student. Same phone (or name) merges into
    the same guardian Person — a parent of two students is one row."""
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    guardian = _find_or_create_guardian(db, body.name, body.phone, body.address)
    _guardian_link(db, student_id, guardian, body.relationship)
    db.commit()
    return {"id": str(guardian.id), "name": guardian.name,
            "phone": (guardian.payload or {}).get("phone")}


@router.delete("/students/{student_id}/guardians/{guardian_id}")
def remove_student_guardian(
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Unlink the guardian from this student; the guardian Person survives."""
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    result = db.execute(student_guardians.delete().where(
        student_guardians.c.student_id == student_id,
        student_guardians.c.guardian_id == guardian_id,
    ))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="guardian link not found")
    db.commit()
    return {"status": "removed"}


@router.get("/guardians/{guardian_id}")
def get_guardian(
    guardian_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Guardian detail: contact info plus every student under their care."""
    g = db.get(Person, guardian_id)
    if g is None or g.role != "guardian":
        raise HTTPException(status_code=404, detail="guardian not found")
    wards = []
    for person, rel in (
        db.query(Person, student_guardians.c.relationship)
        .join(student_guardians, student_guardians.c.student_id == Person.id)
        .filter(student_guardians.c.guardian_id == guardian_id)
        .order_by(Person.created_at)
        .all()
    ):
        cls = current_class(db, person.id)
        wards.append(
            {
                "id": str(person.id),
                "name": person.name,
                "admission_no": (person.payload or {}).get("admission_no"),
                "relationship": rel,
                "class": class_for_api(cls),
            }
        )
    return {
        "id": str(g.id),
        "name": g.name,
        "phone": (g.payload or {}).get("phone"),
        "address": (g.payload or {}).get("address"),
        "wards": wards,
    }


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


def _subject_color_of_exam(
    db: Session,
    exam_id: str | None,
    subject: str | None,
    colors_cache: dict[str, dict],
) -> str | None:
    """Per-exam subject color from the sitting payload, when configured."""
    if not exam_id or not subject:
        return None
    if exam_id not in colors_cache:
        try:
            exam = db.get(Event, uuid.UUID(exam_id))
        except ValueError:
            colors_cache[exam_id] = {}
            return None
        if exam is None or exam.type != "exam":
            colors_cache[exam_id] = {}
        else:
            raw = (exam.payload or {}).get("subject_colors")
            colors_cache[exam_id] = raw if isinstance(raw, dict) else {}
    color = colors_cache[exam_id].get(subject)
    return color if isinstance(color, str) and color else None


def last_event_summary(db: Session, person_id: uuid.UUID) -> dict | None:
    """Most recent timeline event for list views (scores excluded — same as timeline)."""
    ev = (
        db.query(Event)
        .filter(
            Event.attendees.any(Person.id == person_id),
            Event.type != "score",
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .first()
    )
    if ev is None:
        return None
    return {
        "id": str(ev.id),
        "event_type": ev.type,
        "occurred_at": ev.start_time.isoformat(),
        "payload": ev.payload or {},
    }


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
def list_students(
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    students = (
        students_query(db, user)
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
                "name": s.name,
                "gender": (s.payload or {}).get("gender"),
                "status": _status_of(s),
                "class": class_for_api(cls),
                "last_exam": last_exam_summary(db, s.id),
                "last_event": last_event_summary(db, s.id),
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
    class_id: uuid.UUID | None = None


@router.post("/students", status_code=201)
def create_student(
    body: StudentIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    cls = None
    if body.class_id is not None:
        cls = require_class_in_workspace(db, user, body.class_id)
    else:
        cls = ensure_unassigned_class(db)
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
            "admission_no": admission_no,
            "gender": body.gender or None,
            "birth_date": body.birth_date.isoformat() if body.birth_date else None,
            "address": body.address or None,
        },
    )
    person = Person(
        name=body.name.strip(),
        password_hash=hash_password(uuid.uuid4().hex),
        payload=payload,
    )
    db.add(person)
    db.flush()
    tag_student_workspace(person, user)
    _set_primary_guardian(db, person.id, body.guardian_name, body.guardian_phone)
    db.add(Enrollment(person_id=person.id, class_id=cls.id,
                      valid_from=date.today(), reason="admitted"))
    enrolled_payload = (
        {} if is_unassigned_class(cls) else {"class_name": cls.name}
    )
    create_event(db, event_type="enrolled", title="入学", start_time=utcnow(),
                 payload=enrolled_payload, attendee_ids=[person.id, user.id])
    sync_birthday_event(db, person)
    db.commit()
    return {"id": str(person.id), "admission_no": admission_no, "name": person.name}


@router.get("/students/{student_id}")
def get_student(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    s = require_student_in_workspace(db, user, student_id)
    cls = current_class(db, s.id)
    exam_id_cache: dict = {}
    subject_colors_cache: dict[str, dict] = {}
    scores = []
    for r in _score_events(db, s.id):
        pl = r.payload or {}
        exam_name = _exam_name_of_score(r)
        exam_date = r.start_time.date().isoformat()
        subj = pl.get("subject")
        exam_id = _exam_event_id(db, exam_name, exam_date, exam_id_cache)
        scores.append(
            {
                "result_id": str(r.id),
                "exam_id": exam_id,
                "exam_name": exam_name,
                "exam_date": exam_date,
                "subject": subj,
                "subject_color": _subject_color_of_exam(
                    db, exam_id, subj, subject_colors_cache
                ),
                "score": pl.get("score"),
                "full_score": pl.get("max_score"),
                "status": "absent" if pl.get("absent") else "entered",
            }
        )
    guardians = [
        {
            "id": str(g.id),
            "name": g.name,
            "phone": (g.payload or {}).get("phone"),
            "relationship": rel,
        }
        for g, rel in _guardians_of(db, s.id)
    ]
    return {
        "id": str(s.id),
        "admission_no": (s.payload or {}).get("admission_no"),
        "name": s.name,
        "gender": (s.payload or {}).get("gender"),
        "birth_date": (s.payload or {}).get("birth_date"),
        "guardians": guardians,
        "address": (s.payload or {}).get("address"),
        "status": _status_of(s),
        "class": class_for_api(cls),
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
        .filter(
            Event.attendees.any(Person.id == student_id),
            # score events stay in the 考试成绩 card — one row per subject per
            # exam floods the timeline with rows the scores table shows better
            Event.type != "score",
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .all()
    )
    out = [_event_to_dict(e) for e in rows]
    return out


class EventRecordIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    summary: str = Field(default="", max_length=2000)
    purpose: str | None = None
    occurred_at: datetime | None = None
    done: bool | None = None  # home_visited: mark the visit completed
    # home visits: the guardian persons who attended. Absent (old clients)
    # falls back to the student's guardian of record; present-but-empty means
    # no guardian attended.
    guardian_ids: list[uuid.UUID] = Field(default_factory=list)


@router.post("/students/{student_id}/events", status_code=201)
def create_event_record(
    student_id: uuid.UUID,
    body: EventRecordIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    person = db.get(Person, student_id)
    if person is None or person.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    if body.event_type not in _RECORDABLE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的事件类型")
    if body.event_type != "home_visited" and not body.summary.strip():
        raise HTTPException(status_code=400, detail="请填写说明")
    done = body.done if body.event_type == "home_visited" else None
    payload = validate_event_payload(
        body.event_type,
        _record_payload(body.event_type, body.summary, body.purpose, done=done),
    )
    guardian_people: list[Person] = []
    if body.event_type == "home_visited":
        # a visit involves the guardians who were there: selected guardian
        # persons attend the event, and the payload snapshots their names at
        # visit time (the student's guardian links may change later)
        if "guardian_ids" in body.model_fields_set:
            linked = {g.id for g, _ in _guardians_of(db, person.id)}
            requested = list(dict.fromkeys(body.guardian_ids))
            if not set(requested) <= linked:
                raise HTTPException(status_code=400, detail="监护人不属于该学生")
            by_id = {g.id: g for g, _ in _guardians_of(db, person.id)}
            guardian_people = [by_id[i] for i in requested]
        else:
            # old clients without a guardian picker: the guardian of record
            guardian_people = [g for g, _ in _guardians_of(db, person.id)][:1]
        if guardian_people:
            payload["guardian"] = "、".join(g.name for g in guardian_people)
    event = create_event(
        db,
        event_type=body.event_type,
        title=_record_title(body.event_type),
        start_time=body.occurred_at or utcnow(),
        payload=payload,
        # the record involves its student, the guardians who attended,
        # and the teacher who made it
        attendee_ids=[person.id, *[g.id for g in guardian_people], user.id],
    )
    if body.event_type == "home_visited" and (payload or {}).get("done"):
        _maybe_apply_home_visit_tag(db, person.id, user)
    db.commit()
    return {"id": str(event.id), "status": "created"}


class CommentIn(BaseModel):
    student_id: uuid.UUID
    notes: str = Field(min_length=1, max_length=2000)
    mentioned_student_ids: list[uuid.UUID] = Field(default_factory=list)
    occurred_at: datetime | None = None


@router.post("/comments", status_code=201)
def create_comment(
    body: CommentIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Teacher remark on a student; mentioned students also see it on their timeline."""
    primary = db.get(Person, body.student_id)
    if primary is None or primary.role != "student":
        raise HTTPException(status_code=404, detail="student not found")
    mention_ids = [i for i in dict.fromkeys(body.mentioned_student_ids) if i != body.student_id]
    mentioned = _resolve_roster(db, mention_ids)
    notes = body.notes.strip()
    payload_data: dict = {
        "notes": notes,
        "about": {"id": str(primary.id), "name": primary.name},
    }
    if mentioned:
        payload_data["mentioned"] = [{"id": str(s.id), "name": s.name} for s in mentioned]
    payload = validate_event_payload("comment", payload_data)
    event = create_event(
        db,
        event_type="comment",
        title=_record_title("comment"),
        start_time=body.occurred_at or utcnow(),
        payload=payload,
        attendee_ids=[primary.id, *[s.id for s in mentioned], user.id],
    )
    db.commit()
    return {"id": str(event.id), "student_id": str(primary.id), "status": "created"}


class CommentUpdateIn(BaseModel):
    notes: str = Field(min_length=1, max_length=2000)
    mentioned_student_ids: list[uuid.UUID] = Field(default_factory=list)
    occurred_at: datetime | None = None


@router.patch("/comments/{event_id}")
def update_comment(
    event_id: uuid.UUID,
    body: CommentUpdateIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    ev = db.get(Event, event_id)
    if ev is None or ev.type != "comment":
        raise HTTPException(status_code=404, detail="comment not found")
    primary = _comment_primary(db, ev)
    old = ev.payload or {}
    mention_ids = [
        i for i in dict.fromkeys(body.mentioned_student_ids)
        if str(i) != str(primary.id)
    ]
    mentioned = _resolve_roster(db, mention_ids)
    notes = body.notes.strip()
    payload = validate_event_payload(
        "comment",
        {
            "notes": notes,
            "about": {"id": str(primary.id), "name": primary.name},
            "mentioned": [{"id": str(s.id), "name": s.name} for s in mentioned] or None,
        },
    )
    ev.payload = payload
    ev.start_time = body.occurred_at or ev.start_time
    teachers = [p for p in ev.attendees if p.role == "teacher"]
    ev.attendees = [primary, *mentioned, *teachers]
    db.commit()
    return {"id": str(ev.id), "student_id": str(primary.id), "status": "updated"}


@router.delete("/comments/{event_id}")
def delete_comment(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if ev is None or ev.type != "comment":
        raise HTTPException(status_code=404, detail="comment not found")
    db.delete(ev)
    db.commit()
    return {"ok": True}


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


@router.get("/events")
def list_events(
    type: str | None = None,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """我的事件: every Event the signed-in person attends, newest first.

    Events carry participant sets (person_events) — an exam sitting involves
    the creating teacher plus its students, a home visit the teacher, student
    and guardian, a note the teacher and student — so "my events" is
    attendance, not a school-wide listing. `type` narrows the feed to one
    event type (the 事件 page reads ?type=activity, the 家访 page
    ?type=home_visited). students lists every student attendee so multi-
    student activities can render the whole roster; student_id/name stay as
    the primary-student shortcut (the sole student attendee, null for
    sittings and multi-student activities).
    """
    conds = [person_events.c.person_id == user.id]
    if type is not None:
        conds.append(Event.type == type)
    rows = (
        db.query(Event)
        .join(person_events, person_events.c.event_id == Event.id)
        .filter(*conds)
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .limit(200)
        .all()
    )
    students: dict[uuid.UUID, list[Person]] = {}
    if rows:
        for event_id, person in (
            db.query(person_events.c.event_id, Person)
            .join(Person, Person.id == person_events.c.person_id)
            .filter(
                person_events.c.event_id.in_([e.id for e in rows]),
                Person.payload["role"].as_string() == "student",
            )
            .order_by(Person.payload["admission_no"].as_string())
            .all()
        ):
            students.setdefault(event_id, []).append(person)
    out = []
    for ev in rows:
        roster = students.get(ev.id, [])
        # link the student timeline only when the event IS about one student —
        # a sitting with its whole roster has no primary student
        student = roster[0] if len(roster) == 1 else None
        out.append(
            {
                "id": str(ev.id),
                "title": ev.title,
                "student_id": str(student.id) if student else None,
                "student_name": student.name if student else None,
                "students": [
                    {"id": str(s.id), "name": s.name}
                    for s in roster
                ],
                "event_type": ev.type,
                "occurred_at": ev.start_time.isoformat(),
                "actor": None,
                "payload": ev.payload or {},
            }
        )
    return out


class ActivityIn(BaseModel):
    """A 普通事件 (competition, activity, ...) — the events-page write path."""

    title: str = Field(min_length=1, max_length=100)
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    student_ids: list[uuid.UUID] = Field(default_factory=list)


class ActivityUpdateIn(BaseModel):
    """PATCH shape: every field optional; student_ids present-but-null clears
    the roster (presence in model_fields_set drives the semantics)."""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    student_ids: list[uuid.UUID] | None = None


def _resolve_roster(db: Session, student_ids: list[uuid.UUID]) -> list[Person]:
    """Deduped, order-preserving student Persons for the given ids; 404 on
    unknown ids, 400 when a non-student sneaks in."""
    ids = list(dict.fromkeys(student_ids))
    if not ids:
        return []
    found = db.query(Person).filter(Person.id.in_(ids)).all()
    by_id = {p.id: p for p in found}
    if any(i not in by_id for i in ids):
        raise HTTPException(status_code=404, detail="student not found")
    bad = [p for p in by_id.values() if p.role != "student"]
    if bad:
        raise HTTPException(status_code=400, detail="只有学生可以作为参与者")
    return [by_id[i] for i in ids]


def _activity_or_404(db: Session, event_id: uuid.UUID) -> Event:
    """The events page owns 普通事件 only — visits/exams have their own editors."""
    e = db.get(Event, event_id)
    if e is None or e.type != "activity":
        raise HTTPException(status_code=404, detail="event not found")
    return e


def _event_students(db: Session, event_id: uuid.UUID) -> list[Person]:
    return (
        db.query(Person)
        .join(person_events, person_events.c.person_id == Person.id)
        .filter(
            person_events.c.event_id == event_id,
            Person.payload["role"].as_string() == "student",
        )
        .order_by(Person.payload["admission_no"].as_string())
        .all()
    )


def _comment_primary(db: Session, ev: Event) -> Person:
    """Student the comment is about — from payload.about, or infer for legacy rows."""
    payload = ev.payload or {}
    about = payload.get("about") or {}
    if about.get("id"):
        primary = db.get(Person, uuid.UUID(str(about["id"])))
        if primary is not None and primary.role == "student":
            return primary
    mentioned_ids = {str(m["id"]) for m in (payload.get("mentioned") or [])}
    for student in _event_students(db, ev.id):
        if str(student.id) not in mentioned_ids:
            return student
    students = _event_students(db, ev.id)
    if not students:
        raise HTTPException(status_code=404, detail="comment not found")
    return students[0]


def _comment_out(db: Session, ev: Event) -> dict:
    primary = _comment_primary(db, ev)
    payload = ev.payload or {}
    return {
        "id": str(ev.id),
        "student_id": str(primary.id),
        "student_name": primary.name,
        "notes": payload.get("notes") or "",
        "mentioned": payload.get("mentioned") or [],
        "occurred_at": ev.start_time.isoformat(),
    }


@router.get("/comments/{event_id}")
def get_comment(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if ev is None or ev.type != "comment":
        raise HTTPException(status_code=404, detail="comment not found")
    return _comment_out(db, ev)


def _activity_out(db: Session, e: Event) -> dict:
    return {
        "id": str(e.id),
        "title": e.title,
        "event_type": e.type,
        "occurred_at": e.start_time.isoformat(),
        "notes": (e.payload or {}).get("notes"),
        "students": [{"id": str(s.id), "name": s.name} for s in _event_students(db, e.id)],
    }


@router.get("/events/{event_id}")
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    e = _activity_or_404(db, event_id)
    return _activity_out(db, e)


@router.patch("/events/{event_id}")
def update_event(
    event_id: uuid.UUID,
    body: ActivityUpdateIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    e = _activity_or_404(db, event_id)
    if "title" in body.model_fields_set:
        title = (body.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="事件名称不能为空")
        e.title = title
    if "occurred_at" in body.model_fields_set and body.occurred_at is not None:
        e.start_time = body.occurred_at
    if "notes" in body.model_fields_set:
        e.payload = validate_event_payload("activity", {"notes": body.notes})
    if "student_ids" in body.model_fields_set:
        roster = _resolve_roster(db, body.student_ids or [])
        # the recording teacher stays a participant; the student roster is
        # replaced wholesale (copy-assign, relationship sees the change)
        teachers = [p for p in e.attendees if p.role != "student"]
        e.attendees = [*teachers, *roster]
    db.commit()
    db.refresh(e)
    return _activity_out(db, e)


@router.delete("/events/{event_id}")
def delete_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Deletes the activity Event; person_events rows cascade with it."""
    e = _activity_or_404(db, event_id)
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/events", status_code=201)
def create_activity(
    body: ActivityIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="事件名称不能为空")
    roster = _resolve_roster(db, body.student_ids)
    event = create_event(
        db,
        event_type="activity",
        title=title,
        start_time=body.occurred_at or utcnow(),
        payload=validate_event_payload("activity", {"notes": body.notes}),
        # the event involves the teacher recording it plus its students
        attendee_ids=[user.id, *[p.id for p in roster]],
    )
    db.commit()
    return {"id": str(event.id), "status": "created"}


@router.get("/teachers/me/event-types")
def my_event_types(db: Session = Depends(get_db)):
    """The manual record types (the old recently-used-custom-types list died
    with free-form event types — the event table now CHECK-constrains type)."""
    return sorted(MANUAL_EVENT_TYPES)


def _event_to_dict(e: Event) -> dict:
    # Event has no actor column in the new schema, so actor/actor_teacher_id
    # are always None (keys kept for API-shape stability)
    payload = e.payload or {}
    occurred_at = e.start_time
    if e.type == "birthday":
        birth_raw = payload.get("birth_date")
        if birth_raw:
            occurred_at = datetime.combine(
                next_birthday_date(date.fromisoformat(birth_raw)),
                time(9, 0),
            )
    return {
        "id": str(e.id),
        "event_type": e.type,
        "occurred_at": occurred_at.isoformat(),
        "actor": None,
        "payload": payload,
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


def _update_system_event_meta(ev: Event, body: EventRecordIn) -> None:
    """Allow date + free-text notes on auto-generated events; type is fixed."""
    if body.event_type != ev.type:
        raise HTTPException(status_code=400, detail="cannot change system event type")
    payload = dict(ev.payload or {})
    if body.occurred_at is not None:
        ev.start_time = body.occurred_at
    notes = body.summary.strip()
    if notes:
        payload["notes"] = notes
    else:
        payload.pop("notes", None)
    ev.payload = validate_event_payload(ev.type, payload)


@router.patch("/students/{student_id}/events/{event_id}")
def update_event(
    student_id: uuid.UUID,
    event_id: uuid.UUID,
    body: EventRecordIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
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
    if ev.type == "birthday":
        raise HTTPException(status_code=400, detail="生日由系统自动管理")
    if ev.type in SYSTEM_EVENT_TYPES:
        _update_system_event_meta(ev, body)
        db.commit()
        db.refresh(ev)
        return {"id": str(ev.id), "status": "updated"}
    old_payload = dict(ev.payload or {})
    if body.event_type not in _RECORDABLE_TYPES:
        raise HTTPException(status_code=400, detail="不支持的事件类型")
    if ev.type != "home_visited" and not body.summary.strip():
        raise HTTPException(status_code=400, detail="请填写说明")
    was_done = old_payload.get("done") is True
    done = body.done if ev.type == "home_visited" and "done" in body.model_fields_set else None
    ev.type = body.event_type
    ev.title = _record_title(body.event_type)
    ev.start_time = body.occurred_at or ev.start_time
    # copy-modify-reassign: JSON columns don't see in-place mutation
    ev.payload = validate_event_payload(
        body.event_type,
        _record_payload(
            body.event_type, body.summary, body.purpose,
            old_payload, done=done,
        ),
    )
    if ev.type == "home_visited" and not was_done and (ev.payload or {}).get("done"):
        _maybe_apply_home_visit_tag(db, student_id, user)
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
    admission_no: str | None = Field(default=None, min_length=1, max_length=40)
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
        s.name = body.name.strip()
    if body.admission_no is not None:
        admission_no = body.admission_no.strip()
        if not admission_no:
            raise HTTPException(status_code=400, detail="请填写学号")
        current_no = (payload.get("admission_no") or "").strip()
        if admission_no != current_no and _admission_no_in_use(
            db, admission_no, exclude_id=student_id,
        ):
            raise HTTPException(status_code=400, detail="学号已被使用")
        payload["admission_no"] = admission_no
    if body.gender is not None:
        payload["gender"] = body.gender or None
    if body.birth_date is not None:
        payload["birth_date"] = body.birth_date.isoformat()
    if body.address is not None:
        payload["address"] = body.address or None
    if body.status is not None:
        if body.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")
        payload["is_active"] = body.status == "active"
    s.payload = validate_person_payload("student", payload)

    # Guardian upsert: name/phone drive the linked guardian Person (if either
    # is supplied) — see _set_primary_guardian for the merge/link semantics.
    if body.guardian_name is not None or body.guardian_phone is not None:
        _set_primary_guardian(db, s.id, body.guardian_name, body.guardian_phone)

    # Class change: close current enrollment, open a new one, record event.
    if "class_id" in body.model_fields_set:
        if body.class_id is None:
            new_cls = ensure_unassigned_class(db)
        else:
            new_cls = db.get(Class, body.class_id)
            if new_cls is None or is_unassigned_class(new_cls):
                raise HTTPException(status_code=400, detail="class not found")
        current = current_class(db, s.id)
        if current is None or current.id != new_cls.id:
            old_enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.person_id == student_id, Enrollment.valid_to.is_(None))
                .first()
            )
            old_name = (
                None if current is None or is_unassigned_class(current) else current.name
            )
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
            new_name = None if is_unassigned_class(new_cls) else new_cls.name
            if old_name is not None or new_name is not None:
                create_event(
                    db,
                    event_type="class_moved",
                    title="加入班级" if old_name is None else "转班",
                    start_time=utcnow(),
                    payload={"from_class": old_name, "to_class": new_name},
                    attendee_ids=[s.id],
                )

    sync_birthday_event(db, s)
    db.commit()
    cls = current_class(db, s.id)
    return {
        "id": str(s.id),
        "admission_no": (s.payload or {}).get("admission_no"),
        "name": s.name,
        "gender": (s.payload or {}).get("gender"),
        "status": _status_of(s),
        "class": class_for_api(cls),
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
        sync_birthday_event(db, s)
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
