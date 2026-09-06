"""Classes: CRUD plus averages assembled from score Events.

Class columns/roster are relational (Class/Enrollment — current state); the
averaging views aggregate the class's students' score Events
(type="score", title "<exam name>·<subject>", payload subject/score). The
shared sitting/averages helpers live in exams.py — this file imports them.

Attribution: every class average — list avg_trend, class-detail trend, and
/exams/{id}/averages alike — attributes each score to the roster enrolled at
the exam date (the old rule), via _roster_at / the equivalent join.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import RECORD_EVENT_TYPES
from ..models import Class, Enrollment, Event, Person, person_events
from .exams import exam_events, find_exam_event, subject_averages

router = APIRouter(
    tags=["classes"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)


def class_out(
    c: Class,
    teacher: Person | None,
    students: list[Person],
    visited: set[uuid.UUID] | None = None,
) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "grade_level": c.grade_level,
        "academic_year": c.academic_year,
        "homeroom_teacher_id": str(c.homeroom_person_id) if c.homeroom_person_id else None,
        "homeroom_teacher": teacher.name if teacher else None,
        "student_count": len(students),
        "students": [
            {
                "id": str(s.id),
                "name": s.name,
                "gender": (s.payload or {}).get("gender"),
                "admission_no": (s.payload or {}).get("admission_no"),
                "home_visited": s.id in (visited or set()),
            }
            for s in students
        ],
    }


def _visited_ids(db: Session, person_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not person_ids:
        return set()
    rows = (
        db.query(person_events.c.person_id)
        .join(Event, Event.id == person_events.c.event_id)
        .filter(
            Event.type == "home_visited",
            person_events.c.person_id.in_(person_ids),
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _recent_events(db: Session, person_ids: list[uuid.UUID], limit: int = 50) -> list[dict]:
    if not person_ids:
        return []
    rows = (
        db.query(Event, Person)
        .join(person_events, person_events.c.event_id == Event.id)
        .join(Person, Person.id == person_events.c.person_id)
        .filter(
            person_events.c.person_id.in_(person_ids),
            Event.type.in_(list(RECORD_EVENT_TYPES)),
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(ev.id),
            "student_id": str(person.id),
            "student_name": person.name,
            "event_type": ev.type,
            "occurred_at": ev.start_time.isoformat(),
        }
        for ev, person in rows
    ]


def _roster_at(db: Session, class_id: uuid.UUID, day: date) -> list[uuid.UUID]:
    """Student ids enrolled in the class on `day` (the old attribution rule)."""
    return [
        row[0]
        for row in db.query(Enrollment.person_id)
        .filter(
            Enrollment.class_id == class_id,
            Enrollment.valid_from <= day,
            or_(Enrollment.valid_to.is_(None), Enrollment.valid_to >= day),
        )
        .all()
    ]


def _avg_trend(db: Session, class_id: uuid.UUID) -> list[dict]:
    """Chronological per-sitting per-subject class averages; roster
    attribution uses the enrollment valid at each exam date (the old rule,
    same as the class-detail trend and the exam averages page). exam_id
    resolves the sitting Event by title + date (None when there is no such
    row, mirroring students.py)."""
    # candidate sittings: entered score events school-wide, deduped to one
    # (exam name, date) per sitting — score titles vary per subject
    sittings = sorted(
        {(t.rsplit("·", 1)[0] if "·" in t else t, s.date())
         for t, s in db.query(Event.title, Event.start_time)
                        .filter(Event.type == "score").all()},
        key=lambda pair: (pair[1], pair[0]),
    )
    out = []
    for exam_name, day in sittings:
        person_ids = _roster_at(db, class_id, day)
        if not person_ids:
            continue
        averages = {
            subject: round(float(agg["avg"]), 1)
            for subject, agg in sorted(
                subject_averages(db, exam_name, day, person_ids=person_ids).items()
            )
            if agg["avg"] is not None
        }
        if not averages:
            continue
        exam = find_exam_event(db, exam_name, day)
        out.append(
            {
                "exam_id": str(exam.id) if exam else None,
                "exam_name": exam_name,
                "exam_date": day.isoformat(),
                "averages": averages,
            }
        )
    return out


def current_students(db: Session, class_id: uuid.UUID) -> list[Person]:
    return (
        db.query(Person)
        .join(Enrollment, Enrollment.person_id == Person.id)
        .filter(Enrollment.class_id == class_id, Enrollment.valid_to.is_(None))
        .order_by(Person.payload["admission_no"].as_string())
        .all()
    )


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    grade_level: int = Field(ge=1, le=12)
    academic_year: str = Field(min_length=4, max_length=20)
    homeroom_teacher_id: uuid.UUID | None = None


def _validate_homeroom(db: Session, teacher_id: uuid.UUID | None) -> None:
    if teacher_id is None:
        return
    u = db.get(Person, teacher_id)
    if u is None or u.role != "teacher":
        raise HTTPException(status_code=400, detail="teacher not found")


def _check_duplicate(db: Session, name: str, academic_year: str,
                     exclude_id: uuid.UUID | None = None) -> None:
    query = db.query(Class).filter(Class.name == name, Class.academic_year == academic_year)
    if exclude_id is not None:
        query = query.filter(Class.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="该学年已存在同名班级")


@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    out = []
    for c in db.query(Class).order_by(Class.grade_level, Class.name).all():
        teacher = db.get(Person, c.homeroom_person_id) if c.homeroom_person_id else None
        students = current_students(db, c.id)
        ids = [s.id for s in students]
        visited = _visited_ids(db, ids)
        base = class_out(c, teacher, students, visited)
        base["avg_trend"] = _avg_trend(db, c.id)
        base["recent_events"] = _recent_events(db, ids)
        out.append(base)
    return out


@router.post("/classes", status_code=201)
def create_class(
    body: ClassIn,
    db: Session = Depends(get_db),
    current: Person = Depends(get_current_person),
):
    _validate_homeroom(db, body.homeroom_teacher_id)
    _check_duplicate(db, body.name.strip(), body.academic_year.strip())
    c = Class(
        name=body.name.strip(),
        grade_level=body.grade_level,
        academic_year=body.academic_year.strip(),
        homeroom_person_id=body.homeroom_teacher_id,
    )
    db.add(c)
    db.commit()
    teacher = db.get(Person, c.homeroom_person_id) if c.homeroom_person_id else None
    return class_out(c, teacher, [])


@router.get("/classes/{class_id}")
def get_class(class_id: uuid.UUID, db: Session = Depends(get_db)):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    teacher = db.get(Person, c.homeroom_person_id) if c.homeroom_person_id else None

    # per-sitting, per-subject class averages; roster attribution uses the
    # enrollment valid at each exam date (same rule as the exam averages page)
    exams = exam_events(db)
    index_of = {e.id: i for i, e in enumerate(exams)}
    per_subject: dict[str, dict] = {}
    overall: dict[str, dict] = {}
    for e in exams:
        day = e.start_time.date()
        person_ids = _roster_at(db, class_id, day)
        if not person_ids:
            continue
        for subject, agg in sorted(
            subject_averages(db, e.title, day, person_ids=person_ids).items()
        ):
            if agg["avg"] is None:
                continue
            full = float(agg["full"] or 0)
            rec = per_subject.setdefault(
                subject, {"full_score": 0.0, "values": [None] * len(exams)}
            )
            rec["full_score"] = max(rec["full_score"], full)
            if e.id in index_of:
                rec["values"][index_of[e.id]] = round(float(agg["avg"]), 1)
            o = overall.setdefault(subject, {"full_score": 0.0, "sum": 0.0, "count": 0})
            o["full_score"] = max(o["full_score"], full)
            o["sum"] += float(agg["avg"])
            o["count"] += 1

    return {
        "class": {
            "id": str(c.id),
            "name": c.name,
            "grade_level": c.grade_level,
            "academic_year": c.academic_year,
            "homeroom_teacher_id": str(c.homeroom_person_id) if c.homeroom_person_id else None,
            "homeroom_teacher": teacher.name if teacher else None,
        },
        "students": [
            {"id": str(s.id), "name": s.name,
             "gender": (s.payload or {}).get("gender"),
             "admission_no": (s.payload or {}).get("admission_no")}
            for s in current_students(db, class_id)
        ],
        "trend": {
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
        },
        "averages": [
            {
                "subject": subject,
                "avg": round(rec["sum"] / rec["count"], 1) if rec["count"] else None,
                "count": rec["count"],
                "full_score": rec["full_score"],
            }
            for subject, rec in sorted(overall.items())
        ],
    }


@router.patch("/classes/{class_id}")
def update_class(
    class_id: uuid.UUID,
    body: ClassIn,
    db: Session = Depends(get_db),
    current: Person = Depends(get_current_person),
):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    _validate_homeroom(db, body.homeroom_teacher_id)
    _check_duplicate(db, body.name.strip(), body.academic_year.strip(), exclude_id=class_id)
    c.name = body.name.strip()
    c.grade_level = body.grade_level
    c.academic_year = body.academic_year.strip()
    c.homeroom_person_id = body.homeroom_teacher_id
    db.commit()
    teacher = db.get(Person, c.homeroom_person_id) if c.homeroom_person_id else None
    return class_out(c, teacher, current_students(db, class_id))


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Person = Depends(get_current_person),
):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    if db.query(Enrollment).filter(Enrollment.class_id == class_id).first() is not None:
        raise HTTPException(status_code=409, detail="班级内仍有学生或历史记录，无法删除")
    db.delete(c)
    db.commit()
    return {"ok": True}
