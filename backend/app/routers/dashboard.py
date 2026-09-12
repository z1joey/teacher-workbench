"""Dashboard: month calendar and the home summary, read off Event rows.

The calendar mirrors the old behavior: exam sittings (type="exam") plus the
teacher-written records (RECORD_EVENT_TYPES) in one month — the old calendar
carried no birthdays, so none are projected here. Recurrence is gone with the
StudentEvent column (keys it appeared in keep the rest of their shape).

The summary recomputes counts over the new tables: students = active student
Persons, exams = sitting Events, interactions = manual record Events. Score
Events are per-student-per-subject rows with no old-world counterpart in the
recent-events digest, so they (and multi-attendee sitting Events) are skipped
there.
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..display_name import teacher_display_name
from ..database import get_db
from ..deps import get_current_person
from ..eventing import MANUAL_EVENT_TYPES, birthday_in_month
from ..models import Class, Event, Person, person_events
from ..unassigned import is_unassigned_class
from ..workspace import classes_query, students_query, workspace_id

router = APIRouter(
    tags=["dashboard"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)

# timeline digest rows: old recent_events listed StudentEvents (records,
# birthdays, system notes) — sittings and per-subject score rows are not that
_DIGEST_EXCLUDED_TYPES = ("exam", "score")

# digest rows are student-centric: teachers and guardians attend events too,
# but they must never surface as the row's "student" (a teacher row would
# render as a student named 陈老师 linking to a non-student page)
_STUDENT_ATTENDEE = Person.payload["role"].as_string() == "student"


@router.get("/calendar")
def month_calendar(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Home-page month calendar: exams + teacher-written records in one month."""
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="month out of range")
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    items = []
    lo = datetime.combine(first, time.min)
    hi = datetime.combine(last, time.max)
    wid = workspace_id(user)
    # 毕业/停用学生的生日不再出现在日历（学生离校后自动移除）
    active_student = or_(
        Person.payload["is_active"].as_boolean().is_(None),
        Person.payload["is_active"].as_boolean().is_not(False),
    )
    # multi-day sittings appear on every day of their span (中考/高考 style)
    for e in (
        db.query(Event)
        .filter(
            Event.type == "exam",
            Event.attendees.any(Person.id == user.id),
            Event.start_time <= hi,
            func.coalesce(Event.end_time, Event.start_time) >= lo,
        )
        .all()
    ):
        day = e.start_time.date()
        last_day = (e.end_time or e.start_time).date()
        while day <= last_day:
            items.append({"date": day.isoformat(), "kind": "exam",
                          "id": str(e.id), "name": e.title})
            day += timedelta(days=1)
    rows = (
        db.query(Event, Person)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
            .filter(
                Event.type.in_(list(MANUAL_EVENT_TYPES)),
                _STUDENT_ATTENDEE,
                Person.payload["workspace_id"].as_string() == wid,
                # 已毕业学生的记录不上首页（数据保留，档案时间线仍可查看）
                Person.payload["graduated_at"].as_string().is_(None),
                Event.start_time >= lo,
                Event.start_time <= hi,
            )
        .all()
    )
    for ev, student in rows:
        if ev.type == "comment":
            about = (ev.payload or {}).get("about") or {}
            if about.get("id") and str(student.id) != str(about["id"]):
                continue
        items.append({
            "date": ev.start_time.date().isoformat(),
            "kind": "record",
            "id": str(ev.id),
            "event_type": ev.type,
            "student_id": str(student.id),
            "student_name": student.name,
            "actor": None,  # the actor column is gone (see students.py)
            "payload": ev.payload or {},
        })
    user_payload = user.payload or {}
    if user_payload.get("role") == "teacher" and user_payload.get("calendar_birthdays", True):
        seen_birthday_students: set = set()
        for ev, student in (
            db.query(Event, Person)
            .join(person_events, person_events.c.event_id == Event.id)
            .join(Person, Person.id == person_events.c.person_id)
            .filter(
                Event.type == "birthday",
                _STUDENT_ATTENDEE,
                Person.payload["workspace_id"].as_string() == wid,
                active_student,
            )
            .order_by(Event.created_at.asc(), Event.id.asc())
            .all()
        ):
            if student.id in seen_birthday_students:
                continue
            seen_birthday_students.add(student.id)
            birth_raw = (ev.payload or {}).get("birth_date")
            if not birth_raw:
                continue
            bday = birthday_in_month(date.fromisoformat(birth_raw), year, month)
            if bday is None:
                continue
            items.append({
                "date": bday.isoformat(),
                "kind": "record",
                "id": str(ev.id),
                "event_type": "birthday",
                "student_id": str(student.id),
                "student_name": student.name,
                "actor": None,
                "payload": ev.payload or {},
            })
    items.sort(key=lambda i: i["date"])
    return {"year": year, "month": month, "items": items}


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    active = or_(
        Person.payload["is_active"].as_boolean().is_(None),
        Person.payload["is_active"].as_boolean().is_not(False),
    )
    wid = workspace_id(user)
    student_q = students_query(db, user).filter(active)
    counts = {
        "students": student_q.count(),
        "classes": classes_query(db, user).count(),
        "exams": (
            db.query(Event)
            .filter(Event.type == "exam", Event.attendees.any(Person.id == user.id))
            .count()
        ),
        "interactions": (
            db.query(Event)
            .filter(
                Event.type.in_(list(MANUAL_EVENT_TYPES)),
                Event.attendees.any(
                    Person.id.in_(
                        db.query(Person.id).filter(
                            Person.payload["role"].as_string() == "student",
                            Person.payload["workspace_id"].as_string() == wid,
                        )
                    )
                ),
            )
            .count()
        ),
    }
    recent = (
        db.query(Event)
        .filter(
            Event.type.notin_(list(_DIGEST_EXCLUDED_TYPES)),
            Event.attendees.any(Person.id == user.id),
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .limit(24)
        .all()
    )
    # one row per Event with its student roster — teacher/guardian attendees
    # stay out of the digest (rows are student-centric, see _STUDENT_ATTENDEE)
    roster_by_event: dict = {}
    if recent:
        for event_id, person in (
            db.query(person_events.c.event_id, Person)
            .join(Person, Person.id == person_events.c.person_id)
            .filter(
                person_events.c.event_id.in_([e.id for e in recent]),
                _STUDENT_ATTENDEE,
            )
            .order_by(Person.payload["admission_no"].as_string())
            .all()
        ):
            roster_by_event.setdefault(event_id, []).append(person)
    workspace_student_ids = {
        row.id for row in students_query(db, user).with_entities(Person.id).all()
    }
    digest = []
    for event in recent:
        roster = [
            s for s in roster_by_event.get(event.id, [])
            if s.id in workspace_student_ids
            # 已毕业学生不上首页摘要（事件仍有其他在读学生时保留该事件）
            and not (s.payload or {}).get("graduated_at")
        ]
        if not roster:
            continue
        digest.append(event)
        if len(digest) >= 8:
            break
    today = date.today()
    # 全部学生参与者都已毕业的考试不再列入「即将考试」
    active_exam_student = and_(
        Person.payload["role"].as_string() == "student",
        Person.payload["graduated_at"].as_string().is_(None),
    )
    upcoming = (
        db.query(Event)
        .filter(
            Event.type == "exam",
            Event.attendees.any(Person.id == user.id),
            Event.attendees.any(active_exam_student),
            Event.start_time >= datetime.combine(today, time.min),
        )
        .order_by(Event.start_time)
        .limit(3)
        .all()
    )
    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "display_name": teacher_display_name(user.name),
        },
        "counts": counts,
        "upcoming_exams": [
            {
                "id": str(exam.id),
                "name": exam.title,
                "exam_date": exam.start_time.date().isoformat(),
                "end_date": (exam.end_time.date().isoformat() if exam.end_time else None),
            }
            for exam in upcoming
        ],
        "recent_events": [
            {
                "id": str(event.id),
                "title": event.title,
                "event_type": event.type,
                "occurred_at": event.start_time.isoformat(),
                "payload": event.payload or {},
                "students": [
                    {"id": str(s.id), "name": s.name}
                    for s in roster_by_event.get(event.id, [])
                ],
            }
            for event in digest
        ],
    }
