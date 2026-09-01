from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..models import Class, Exam, HomeVisit, Student, StudentEvent, Teacher

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
        "home_visits": db.query(HomeVisit).count(),
    }
    follow_ups = (
        db.query(HomeVisit, Student.name)
        .join(Student, Student.id == HomeVisit.student_id)
        .filter(HomeVisit.follow_up_needed.is_(True))
        .order_by(HomeVisit.visited_at.desc())
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
                "exam_type": exam.exam_type,
            }
            for exam in upcoming
        ],
        "follow_ups": [
            {
                "student_id": visit.student_id,
                "student_name": student_name,
                "visited_at": visit.visited_at.isoformat(),
                "purpose": visit.purpose,
                "follow_up_note": visit.follow_up_note,
            }
            for visit, student_name in follow_ups
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
