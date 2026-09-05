"""Exams: a sitting is one Event(type="exam") row, scores are score Events.

The sitting Event is titled with the exam name and dated the first exam day
(start_time 09:00); multi-day sittings (中考/高考 style) put the last day in
end_time. An optional class_id scopes its attendees to that class's
enrolled students (otherwise the whole active student body attends). There
are no ExamSubject rows: the per-subject full_score config posted to
POST/PATCH /exams lives in the sitting Event's registry-validated payload as
payload["full_scores"] ({subject: full score}) — that is where the
score-entry flow reads each subject's max_score from before writing
per-student score Events. description stays plain free text.

Score rows follow the students-router convention: one Event(type="score") per
student per subject, title "<exam name>·<subject>", start_time on the exam's
first day, payload {subject, max_score, score|absent}. With no parent link, a
sitting's scores are matched by title prefix ("{exam.title}·") AND the
sitting's date window (see sitting_score_conds) — the same rule students.py
uses to resolve exam_id. Averages aggregate payload["score"] over entered
rows only (absent=true excluded, score present).

These helpers (sitting_score_conds / subject_averages / find_exam_event) are
the shared sitting/averages vocabulary — classes.py imports them from here
rather than duplicating the aggregation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import create_event
from ..models import Class, Enrollment, Event, Person, person_events
from ..payloads import validate_event_payload

router = APIRouter(
    tags=["exams"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)

EXAM_HOUR = time(9, 0)  # sitting Events are dated the exam day at 09:00


def day_window(start_day: date, end_day: date | None = None) -> tuple[datetime, datetime]:
    """Inclusive window: [00:00 on start_day, 23:59:59.999999 on end_day]
    (single-day when end_day is omitted)."""
    lo = datetime.combine(start_day, time.min)
    hi = datetime.combine(end_day or start_day, time.max)
    return lo, hi


def exam_days(e: Event) -> tuple[date, date]:
    """(first_day, last_day) of a sitting; single-day when end_time is unset."""
    return e.start_time.date(), (e.end_time or e.start_time).date()


def sitting_score_conds(title_prefix: str, start_day: date,
                        end_day: date | None = None) -> list:
    """Score Events of one sitting: title "<prefix>·<subject>", within the
    sitting's date window, entered only — absent=true excluded (validated
    payloads always carry absent:false explicitly, so NULL never occurs) and
    score present."""
    lo, hi = day_window(start_day, end_day)
    return [
        Event.type == "score",
        Event.title.startswith(f"{title_prefix}·", autoescape=True),
        Event.start_time >= lo,
        Event.start_time < hi,
        Event.payload["absent"].as_boolean().is_not(True),
        Event.payload["score"].is_not(None),
    ]


def any_sitting_score_conds(title_prefix: str, start_day: date,
                            end_day: date | None = None) -> list:
    """Score Events of a sitting regardless of entered state (the
    structure-frozen check in PATCH /exams mirrors the old any-ExamResult rule)."""
    lo, hi = day_window(start_day, end_day)
    return [
        Event.type == "score",
        Event.title.startswith(f"{title_prefix}·", autoescape=True),
        Event.start_time >= lo,
        Event.start_time < hi,
    ]


def subject_averages(db: Session, title_prefix: str, start_day: date,
                     end_day: date | None = None,
                     person_ids: list[uuid.UUID] | None = None) -> dict[str, dict]:
    """Per-subject aggregate over one sitting's entered score Events:
    {subject: {avg, min, max, count, full}} — full is the max payload
    max_score (the old ExamSubject.full_score now lives on every score row).
    person_ids restricts the aggregate to those students (class attribution)."""
    subject = Event.payload["subject"].as_string()
    q = (
        db.query(
            subject,
            func.avg(Event.payload["score"].as_numeric(10, 2)),
            func.min(Event.payload["score"].as_numeric(10, 2)),
            func.max(Event.payload["score"].as_numeric(10, 2)),
            func.count(Event.id),
            func.max(Event.payload["max_score"].as_numeric(10, 2)),
        )
        .select_from(Event)
        .join(person_events, person_events.c.event_id == Event.id)
    )
    if person_ids is not None:
        q = q.filter(person_events.c.person_id.in_(person_ids))
    rows = q.filter(*sitting_score_conds(title_prefix, start_day, end_day)).group_by(subject).all()
    return {
        s: {"avg": avg, "min": min_, "max": max_, "count": count, "full": full}
        for s, avg, min_, max_, count, full in rows
    }


def find_exam_event(db: Session, name: str, day: date) -> Event | None:
    """The sitting Event of a name whose [first_day, last_day] contains day
    (students.py resolves score rows' exam_id with the same rule)."""
    return (
        db.query(Event)
        .filter(
            Event.type == "exam",
            Event.title == name,
            Event.start_time <= datetime.combine(day, time.max),
            func.coalesce(Event.end_time, Event.start_time)
            >= datetime.combine(day, time.min),
        )
        .first()
    )


def exam_events(db: Session) -> list[Event]:
    """All sittings, chronological (start_time, then creation order — the old
    auto-increment id tiebreak)."""
    return (
        db.query(Event)
        .filter(Event.type == "exam")
        .order_by(Event.start_time, Event.created_at)
        .all()
    )


def subjects_config(exam: Event) -> list[dict]:
    """The sitting's subjects from the registry-validated payload
    ({"full_scores": {subject: full score}}), serialized to the old response
    shape [{id, subject, full_score}] sorted by subject — [] on missing or
    malformed config. Entry ids are deterministic per (exam, subject) so they
    are stable across reads (the old ExamSubject ids died with the table)."""
    full_scores = (exam.payload or {}).get("full_scores")
    if not isinstance(full_scores, dict):
        return []
    return [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{exam.id}:{subject}")),
            "subject": subject,
            "full_score": full,
        }
        for subject, full in sorted(full_scores.items())
    ]


def full_scores_of(subjects: list["SubjectIn"]) -> dict[str, float]:
    return {s.subject.strip(): s.full_score for s in subjects}


def exam_out(exam: Event) -> dict:
    return {
        "id": str(exam.id),
        "name": exam.title,
        "exam_date": exam.start_time.date().isoformat(),
        "end_date": exam.end_time.date().isoformat() if exam.end_time else None,
        "subjects": sorted(
            (
                {"id": c["id"], "subject": c["subject"], "full_score": c["full_score"]}
                for c in subjects_config(exam)
            ),
            key=lambda s: s["subject"],
        ),
    }


def _attendee_ids(db: Session, class_id: uuid.UUID | None) -> list[uuid.UUID]:
    if class_id is not None:
        return [
            row[0]
            for row in db.query(Enrollment.person_id)
            .filter(Enrollment.class_id == class_id, Enrollment.valid_to.is_(None))
            .all()
        ]
    # school-wide sitting: the active student body attends
    active = or_(
        Person.payload["is_active"].as_boolean().is_(None),
        Person.payload["is_active"].as_boolean().is_not(False),
    )
    return [
        row[0]
        for row in db.query(Person.id)
        .filter(Person.payload["role"].as_string() == "student", active)
        .all()
    ]


class SubjectIn(BaseModel):
    subject: str = Field(min_length=1, max_length=50)
    full_score: float = Field(gt=0, le=1000)


class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exam_date: date
    end_date: date | None = None  # last day of a multi-day sitting
    subjects: list[SubjectIn] = Field(min_length=1)
    class_id: uuid.UUID | None = None  # scope attendees to one class
    term: str | None = None


@router.post("/exams", status_code=201)
def create_exam(
    body: ExamIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    name = body.name.strip()
    if body.end_date is not None and body.end_date < body.exam_date:
        raise HTTPException(status_code=400, detail="结束日期不能早于考试日期")
    # duplicate rule: same-named exam overlapping the [start, end] span
    lo, hi = day_window(body.exam_date, body.end_date)
    overlap = (
        db.query(Event.id)
        .filter(
            Event.type == "exam",
            Event.title == name,
            Event.start_time <= hi,
            func.coalesce(Event.end_time, Event.start_time) >= lo,
        )
        .first()
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="该日期已存在同名考试")
    if body.class_id is not None and db.get(Class, body.class_id) is None:
        raise HTTPException(status_code=400, detail="class not found")
    exam = create_event(
        db,
        event_type="exam",
        title=name,
        start_time=datetime.combine(body.exam_date, EXAM_HOUR),
        end_time=datetime.combine(body.end_date, time.max) if body.end_date else None,
        payload={"term": body.term, "full_scores": full_scores_of(body.subjects)},
        attendee_ids=_attendee_ids(db, body.class_id),
    )
    db.commit()
    return {"id": str(exam.id), "name": exam.title,
            "exam_date": exam.start_time.date().isoformat(),
            "end_date": exam.end_time.date().isoformat() if exam.end_time else None}


@router.get("/exams")
def list_exams(db: Session = Depends(get_db)):
    exams = exam_events(db)
    exams.reverse()  # old listing was exam_date desc
    return [exam_out(e) for e in exams]


@router.get("/exams/trend")
def exams_trend(db: Session = Depends(get_db), user: Person = Depends(get_current_person)):
    """School-wide per-subject averages across sittings (entered scores only)."""
    exams = exam_events(db)
    index_of = {e.id: i for i, e in enumerate(exams)}
    per_subject: dict[str, dict] = {}
    for e in exams:
        start_day, end_day = exam_days(e)
        for subject, agg in subject_averages(
            db, e.title, start_day, end_day
        ).items():
            rec = per_subject.setdefault(
                subject, {"full_score": 0.0, "values": [None] * len(exams)}
            )
            rec["full_score"] = max(rec["full_score"], float(agg["full"] or 0))
            if e.id in index_of and agg["avg"] is not None:
                rec["values"][index_of[e.id]] = round(float(agg["avg"]), 1)
    return {
        "exams": [
            {
                "id": str(e.id),
                "name": e.title,
                "exam_date": e.start_time.date().isoformat(),
            }
            for e in exams
        ],
        "series": [
            {"subject": subject, "values": rec["values"], "full_score": rec["full_score"]}
            for subject, rec in sorted(per_subject.items())
        ],
    }


@router.get("/exams/{exam_id}")
def get_exam(exam_id: uuid.UUID, db: Session = Depends(get_db)):
    e = db.get(Event, exam_id)
    if e is None or e.type != "exam":
        raise HTTPException(status_code=404, detail="exam not found")
    return exam_out(e)


@router.get("/exams/{exam_id}/averages")
def exam_averages(exam_id: uuid.UUID, db: Session = Depends(get_db)):
    exam = db.get(Event, exam_id)
    if exam is None or exam.type != "exam":
        raise HTTPException(status_code=404, detail="exam not found")
    start_day, end_day = exam_days(exam)

    school = [
        {
            "subject": subject,
            "full_score": float(agg["full"]) if agg["full"] is not None else None,
            "avg": round(float(agg["avg"]), 1) if agg["avg"] is not None else None,
            "min": round(float(agg["min"]), 1) if agg["min"] is not None else None,
            "max": round(float(agg["max"]), 1) if agg["max"] is not None else None,
            "count": agg["count"],
        }
        for subject, agg in sorted(
            subject_averages(db, exam.title, start_day, end_day).items()
        )
    ]

    # per-class averages attribute each score to the class roster valid at the
    # exam date (the old enrollment-valid-at-exam_date rule; attribution uses
    # the first day — scores follow the sitting window)
    class_rows = (
        db.query(
            Class.id,
            Class.name,
            Event.payload["subject"].as_string(),
            func.avg(Event.payload["score"].as_numeric(10, 2)),
            func.count(Event.id),
        )
        .select_from(Event)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
        .join(
            Enrollment,
            and_(
                Enrollment.person_id == Person.id,
                Enrollment.valid_from <= start_day,
                or_(Enrollment.valid_to.is_(None), Enrollment.valid_to >= start_day),
            ),
        )
        .join(Class, Class.id == Enrollment.class_id)
        .filter(*sitting_score_conds(exam.title, start_day, end_day))
        .group_by(Class.id, Class.name, Event.payload["subject"].as_string())
        .order_by(Class.name, Event.payload["subject"].as_string())
        .all()
    )

    return {
        "exam": {
            "id": str(exam.id),
            "name": exam.title,
            "exam_date": start_day.isoformat(),
            "end_date": end_day.isoformat() if exam.end_time else None,
        },
        "school": school,
        "classes": [
            {
                "class_id": str(class_id),
                "class_name": class_name,
                "subject": subject,
                "avg": round(float(avg), 1) if avg is not None else None,
                "count": count,
            }
            for class_id, class_name, subject, avg, count in class_rows
        ],
    }


class ExamUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    exam_date: date | None = None
    end_date: date | None = None  # last day of a multi-day sitting
    subjects: list[SubjectIn] | None = None


@router.patch("/exams/{exam_id}")
def update_exam(
    exam_id: uuid.UUID,
    body: ExamUpdateIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    e = db.get(Event, exam_id)
    if e is None or e.type != "exam":
        raise HTTPException(status_code=404, detail="exam not found")

    old_name, (old_start, old_end) = e.title, exam_days(e)
    new_start = body.exam_date or old_start
    # end_date present-but-null clears the span (back to a single day);
    # absent means "no change" (PATCH semantics) — except a single-day
    # sitting has no explicit end, so its implied end follows the start
    if "end_date" in body.model_fields_set:
        new_end = body.end_date or new_start
    elif e.end_time is None:
        new_end = new_start
    else:
        new_end = old_end
    if new_end < new_start:
        raise HTTPException(status_code=400, detail="结束日期不能早于考试日期")

    if body.subjects is not None:
        if (
            db.query(Event.id)
            .filter(*any_sitting_score_conds(old_name, old_start, old_end))
            .first()
            is not None
        ):
            raise HTTPException(status_code=400, detail="考试已有成绩录入，无法修改科目结构")
        # copy-modify-reassign + re-validate: JSON columns don't see in-place
        # mutation, and the config must stay registry-shaped
        payload = dict(e.payload or {})
        payload["full_scores"] = full_scores_of(body.subjects)
        e.payload = validate_event_payload("exam", payload)

    if body.name is not None:
        e.title = body.name.strip()
    if body.exam_date is not None:
        e.start_time = datetime.combine(body.exam_date, e.start_time.time())
    if body.end_date is not None:
        e.end_time = datetime.combine(body.end_date, time.max)
    elif "end_date" in body.model_fields_set:
        e.end_time = None  # explicitly cleared: single-day sitting again

    # renaming / re-dating the sitting must not orphan its scores: the results
    # follow the exam (the old FK behavior — results stayed attached); scores
    # are dated on the first day, so only a start-day shift moves them
    if e.title != old_name or e.start_time.date() != old_start:
        shift = (e.start_time.date() - old_start).days
        for score in (
            db.query(Event)
            .filter(*any_sitting_score_conds(old_name, old_start, old_end))
            .all()
        ):
            subject = score.title.rsplit("·", 1)[-1]
            score.title = f"{e.title}·{subject}"
            score.start_time = score.start_time + timedelta(days=shift)

    db.commit()
    db.refresh(e)
    return exam_out(e)


@router.delete("/exams/{exam_id}")
def delete_exam(
    exam_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Deletes the sitting Event only. Score events are individual rows with
    no parent link, so they deliberately survive the delete (the old cascade
    over exam_subject/exam_result has no equivalent to walk)."""
    e = db.get(Event, exam_id)
    if e is None or e.type != "exam":
        raise HTTPException(status_code=404, detail="exam not found")
    db.delete(e)
    db.commit()
    return {"ok": True}
