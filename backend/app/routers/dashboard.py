from calendar import monthrange
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, type_coerce
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..events import MANUAL_EVENT_TYPES, RECORD_EVENT_TYPES
from ..models import Class, Exam, Student, StudentEvent, User

router = APIRouter(tags=["dashboard"])


@router.get("/calendar")
def month_calendar(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Home-page month calendar: exams + teacher-written records in one month."""
    if not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="month out of range")
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    items = []
    for e in (
        db.query(Exam)
        .filter(Exam.exam_date >= first, Exam.exam_date <= last)
        .all()
    ):
        items.append({"date": e.exam_date.isoformat(), "kind": "exam", "id": e.id, "name": e.name})
    rows = (
        db.query(StudentEvent, Student.name, User.name)
        .join(Student, Student.id == StudentEvent.student_id)
        .outerjoin(User, User.id == StudentEvent.actor_teacher_id)
        .filter(
            StudentEvent.event_type.in_(RECORD_EVENT_TYPES),
            StudentEvent.occurred_at >= datetime.combine(first, time.min),
            StudentEvent.occurred_at <= datetime.combine(last, time.max),
        )
        .all()
    )
    for ev, student_name, actor in rows:
        items.append({
            "date": ev.occurred_at.date().isoformat(),
            "kind": "record",
            "id": ev.id,
            "event_type": ev.event_type,
            "recurrence": ev.recurrence,
            "student_id": ev.student_id,
            "student_name": student_name,
            "actor": actor,
            "payload": ev.payload or {},
        })
    items.sort(key=lambda i: i["date"])
    return {"year": year, "month": month, "items": items}


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    counts = {
        "students": db.query(Student).filter(Student.status == "active").count(),
        "classes": db.query(Class).count(),
        "exams": db.query(Exam).count(),
        # 跟进记录: every teacher-written StudentEvent (visits, talks, notes, …)
        "interactions": db.query(StudentEvent).filter(
            StudentEvent.event_type.in_(MANUAL_EVENT_TYPES)).count(),
    }
    # SQLite（本地开发）把 JSON 存成文本，contains() 渲染为 LIKE 即可匹配；
    # PostgreSQL 的 JSONB 下 contains() 会渲染成非法 SQL，必须用 @> 包含运算符。
    if db.bind.dialect.name == "postgresql":
        follow_up_filter = StudentEvent.payload.op("@>")(
            type_coerce({"follow_up_needed": True}, JSONB)
        )
    else:
        # SQLite stores JSON as TEXT — a LIKE contains() can never match a key
        # nested mid-object; json_extract reads the actual value instead.
        follow_up_filter = func.json_extract(
            StudentEvent.payload, "$.follow_up_needed"
        ) == 1
    follow_ups = (
        db.query(StudentEvent, Student.name)
        .join(Student, Student.id == StudentEvent.student_id)
        .filter(
            follow_up_filter,
        )
        .order_by(StudentEvent.occurred_at.desc())
        .limit(5)
        .all()
    )
    recent = (
        db.query(StudentEvent, Student.name)
        .join(Student, Student.id == StudentEvent.student_id)
        .order_by(StudentEvent.occurred_at.desc(), StudentEvent.id.desc())
        .limit(8)
        .all()
    )
    upcoming = (
        db.query(Exam)
        .filter(Exam.exam_date >= date.today())
        .order_by(Exam.exam_date)
        .limit(3)
        .all()
    )
    return {
        "user": {"id": user.id, "name": user.name},
        "counts": counts,
        "upcoming_exams": [
            {
                "id": exam.id,
                "name": exam.name,
                "exam_date": exam.exam_date.isoformat(),
            }
            for exam in upcoming
        ],
        "follow_ups": [
            {
                "student_id": ev.student_id,
                "student_name": student_name,
                "event_type": ev.event_type,
                "occurred_at": ev.occurred_at.isoformat(),
                "purpose": (ev.payload or {}).get("purpose"),
                "summary": (ev.payload or {}).get("summary"),
                "follow_up_note": (ev.payload or {}).get("follow_up_note"),
            }
            for ev, student_name in follow_ups
        ],
        "recent_events": [
            {
                "id": event.id,
                "student_id": event.student_id,
                "student_name": student_name,
                "event_type": event.event_type,
                "occurred_at": event.occurred_at.isoformat(),
                "payload": event.payload or {},
            }
            for event, student_name in recent
        ],
    }
