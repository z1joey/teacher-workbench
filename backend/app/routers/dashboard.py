"""Dashboard: month calendar and the home summary, read off Event rows.

The calendar mirrors the old behavior: exam sittings (type="exam") plus the
teacher-written records (RECORD_EVENT_TYPES) in one month — the old calendar
carried no birthdays, so none are projected here. Recurrence is gone with the
StudentEvent column (keys it appeared in keep the rest of their shape).

The summary recomputes counts over the new tables: students = active student
Persons, exams = sitting Events, interactions = manual record Events. Score
Events are per-student-per-subject rows with no old-world counterpart in the
recent-events digest, so they (and multi-attendee sitting Events) are skipped
there; follow-ups are home visits whose payload follow_up note is set (the
old follow_up_needed flag collapsed into it — see students.py).
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import MANUAL_EVENT_TYPES, RECORD_EVENT_TYPES
from ..models import Class, Event, Person, person_events

router = APIRouter(
    tags=["dashboard"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)

# timeline digest rows: old recent_events listed StudentEvents (records,
# birthdays, system notes) — sittings and per-subject score rows are not that
_DIGEST_EXCLUDED_TYPES = ("exam", "score")


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
    # multi-day sittings appear on every day of their span (中考/高考 style)
    for e in (
        db.query(Event)
        .filter(
            Event.type == "exam",
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
            Event.type.in_(list(RECORD_EVENT_TYPES)),
            Event.start_time >= lo,
            Event.start_time <= hi,
        )
        .all()
    )
    for ev, student in rows:
        items.append({
            "date": ev.start_time.date().isoformat(),
            "kind": "record",
            "id": str(ev.id),
            "event_type": ev.type,
            "student_id": str(student.id),
            "student_name": (student.payload or {}).get("name"),
            "actor": None,  # the actor column is gone (see students.py)
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
    counts = {
        "students": (
            db.query(Person)
            .filter(Person.payload["role"].as_string() == "student", active)
            .count()
        ),
        "classes": db.query(Class).count(),
        "exams": db.query(Event).filter(Event.type == "exam").count(),
        # 跟进记录: every teacher-written record Event (visits, talks, notes, …)
        "interactions": (
            db.query(Event).filter(Event.type.in_(list(MANUAL_EVENT_TYPES))).count()
        ),
    }
    follow_ups = (
        db.query(Event, Person)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
        .filter(
            Event.type == "home_visited",
            # follow_up_needed collapsed into the follow_up note (students.py);
            # as_string() keeps the NULL compare a plain SQL NULL (a bare
            # JSON-path IS (NOT) NULL binds JSON 'null', matching every row)
            Event.payload["follow_up"].as_string().is_not(None),
        )
        .order_by(Event.start_time.desc())
        .limit(5)
        .all()
    )
    recent = (
        db.query(Event, Person)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
        .filter(Event.type.notin_(list(_DIGEST_EXCLUDED_TYPES)))
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .limit(8)
        .all()
    )
    today = date.today()
    upcoming = (
        db.query(Event)
        .filter(
            Event.type == "exam",
            Event.start_time >= datetime.combine(today, time.min),
        )
        .order_by(Event.start_time)
        .limit(3)
        .all()
    )
    return {
        "user": {"id": str(user.id), "name": (user.payload or {}).get("name")},
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
        "follow_ups": [
            {
                "student_id": str(person.id),
                "student_name": (person.payload or {}).get("name"),
                "event_type": ev.type,
                "occurred_at": ev.start_time.isoformat(),
                "purpose": None,  # no payload slot anymore (see students.py)
                "summary": (ev.payload or {}).get("summary"),
                "follow_up_note": (ev.payload or {}).get("follow_up"),
            }
            for ev, person in follow_ups
        ],
        "recent_events": [
            {
                "id": str(event.id),
                "student_id": str(person.id),
                "student_name": (person.payload or {}).get("name"),
                "event_type": event.type,
                "occurred_at": event.start_time.isoformat(),
                "payload": event.payload or {},
            }
            for event, person in recent
        ],
    }
