from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..models import Class, Exam, Student, StudentEvent, Teacher

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    counts = {
        "students": db.query(Student).filter(Student.status == "active").count(),
        "classes": db.query(Class).count(),
        "exams": db.query(Exam).count(),
        "home_visits": db.query(StudentEvent).filter(StudentEvent.event_type == "home_visited").count(),
    }
    follow_ups = (
        db.query(StudentEvent, Student.name)
        .join(Student, Student.id == StudentEvent.student_id)
        .filter(
            StudentEvent.event_type == "home_visited",
            StudentEvent.payload.contains({"follow_up_needed": True}),
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
        "teacher": {"id": teacher.id, "name": teacher.name},
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
                "visited_at": ev.occurred_at.isoformat(),
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
