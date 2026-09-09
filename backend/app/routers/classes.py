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
from ..eventing import RECORD_EVENT_TYPES, create_event
from ..models._common import utcnow
from ..unassigned import is_unassigned_class
from ..workspace import classes_query, require_class_in_workspace
from ..models import Class, ClassSeating, Enrollment, Event, Person, person_events
from .exams import exam_events, find_exam_event, subject_averages

router = APIRouter(
    tags=["classes"],
    dependencies=[Depends(get_current_person)],  # router-level auth (include pattern)
)


def class_out(
    c: Class,
    students: list[Person],
    visited: set[uuid.UUID] | None = None,
) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "academic_year": c.academic_year,
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
    out = []
    for ev, person in rows:
        if ev.type == "comment":
            about = (ev.payload or {}).get("about") or {}
            if about.get("id") and str(person.id) != str(about["id"]):
                continue
        out.append(
            {
                "id": str(ev.id),
                "student_id": str(person.id),
                "student_name": person.name,
                "event_type": ev.type,
                "occurred_at": ev.start_time.isoformat(),
                "payload": ev.payload or {},
            }
        )
    return out


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
    academic_year: str = Field(min_length=4, max_length=20)


def _check_duplicate(db: Session, name: str, academic_year: str,
                     exclude_id: uuid.UUID | None = None) -> None:
    query = db.query(Class).filter(Class.name == name, Class.academic_year == academic_year)
    if exclude_id is not None:
        query = query.filter(Class.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="该学年已存在同名班级")


@router.get("/classes")
def list_classes(
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    out = []
    for c in classes_query(db, user).order_by(Class.name).all():
        students = current_students(db, c.id)
        ids = [s.id for s in students]
        visited = _visited_ids(db, ids)
        base = class_out(c, students, visited)
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
    _check_duplicate(db, body.name.strip(), body.academic_year.strip())
    c = Class(
        name=body.name.strip(),
        academic_year=body.academic_year.strip(),
        teacher_id=current.id,
    )
    db.add(c)
    db.commit()
    return class_out(c, [])


@router.get("/classes/{class_id}")
def get_class(
    class_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    c = require_class_in_workspace(db, user, class_id)

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
            "academic_year": c.academic_year,
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


class SeatingIn(BaseModel):
    rows: int = Field(ge=1, le=20)
    cols: int = Field(ge=1, le=12)
    # {座位序号(行优先从0起): 学生 id}
    seats: dict[str, uuid.UUID] = Field(default_factory=dict)


@router.get("/classes/{class_id}/seating")
def get_seating(
    class_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    require_class_in_workspace(db, user, class_id)
    row = db.get(ClassSeating, class_id)
    if row is None:
        return {"rows": 0, "cols": 0, "seats": {}}
    return {"rows": row.rows, "cols": row.cols, "seats": row.seats or {}}


def _seat_label(pos: int | None, cols: int) -> str | None:
    """座位序号 → 「第X排第Y列」；None（无座位）原样返回。"""
    if pos is None:
        return None
    return f"第{pos // cols + 1}排第{pos % cols + 1}列"


@router.put("/classes/{class_id}/seating")
def save_seating(
    class_id: uuid.UUID,
    body: SeatingIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """保存座位表。只校验「座位属于本班、一人一座、位置在格内」；学生转班后
    旧座位保留原序号，由前端在名单变化时清掉失效座位。
    任一学生的座位发生变化（首次安排/移动/移出）都会留一条 seat_changed 事件。"""
    require_class_in_workspace(db, user, class_id)
    member_ids = {str(s.id) for s in current_students(db, class_id)}
    seen: set[str] = set()
    for pos, sid in body.seats.items():
        if not pos.isdigit() or int(pos) < 0 or int(pos) >= body.rows * body.cols:
            raise HTTPException(status_code=400, detail="座位位置超出表格范围")
        if str(sid) not in member_ids:
            raise HTTPException(status_code=400, detail="有学生不属于这个班级，不能安排座位")
        if str(sid) in seen:
            raise HTTPException(status_code=400, detail="一个学生只能有一个座位")
        seen.add(str(sid))

    row = db.get(ClassSeating, class_id)
    old_seats = dict(row.seats or {}) if row is not None else {}
    old_cols = row.cols if row is not None else body.cols
    seats = {pos: str(sid) for pos, sid in body.seats.items()}
    if row is None:
        row = ClassSeating(
            class_id=class_id, rows=body.rows, cols=body.cols, seats=seats
        )
        db.add(row)
    else:
        row.rows = body.rows
        row.cols = body.cols
        row.seats = seats

    for sid in sorted(set(old_seats.values()) | set(seats.values())):
        old_pos = next((int(p) for p, v in old_seats.items() if v == sid), None)
        new_pos = next((int(p) for p, v in seats.items() if v == sid), None)
        if old_pos == new_pos:
            continue
        create_event(
            db,
            event_type="seat_changed",
            title="换座位",
            start_time=utcnow(),
            payload={
                "from": _seat_label(old_pos, old_cols),
                "to": _seat_label(new_pos, body.cols),
            },
            attendee_ids=[uuid.UUID(sid)],
        )
    db.commit()
    return {"rows": row.rows, "cols": row.cols, "seats": row.seats or {}}


@router.patch("/classes/{class_id}")
def update_class(
    class_id: uuid.UUID,
    body: ClassIn,
    db: Session = Depends(get_db),
    current: Person = Depends(get_current_person),
):
    c = db.get(Class, class_id)
    if c is None or is_unassigned_class(c):
        raise HTTPException(status_code=404, detail="class not found")
    _check_duplicate(db, body.name.strip(), body.academic_year.strip(), exclude_id=class_id)
    c.name = body.name.strip()
    c.academic_year = body.academic_year.strip()
    db.commit()
    return class_out(c, current_students(db, class_id))


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Person = Depends(get_current_person),
):
    c = db.get(Class, class_id)
    if c is None or is_unassigned_class(c):
        raise HTTPException(status_code=404, detail="class not found")
    if db.query(Enrollment).filter(Enrollment.class_id == class_id).first() is not None:
        raise HTTPException(status_code=409, detail="班级内仍有学生或历史记录，无法删除")
    db.delete(c)
    db.commit()
    return {"ok": True}
