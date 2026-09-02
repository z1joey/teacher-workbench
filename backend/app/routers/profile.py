from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..models import Class, Enrollment, ExamResult, Student, StudentEvent, Teacher

router = APIRouter(tags=["profile"])


def teacher_out(t: Teacher) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "phone": t.phone,
        "email": t.email,
        "subject": t.subject,
        "is_admin": t.is_admin,
    }


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    subject: str | None = None


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), teacher: Teacher = Depends(get_current_teacher)):
    classes = (
        db.query(Class)
        .filter(Class.homeroom_teacher_id == teacher.id)
        .order_by(Class.name)
        .all()
    )
    out_classes = []
    for c in classes:
        students = (
            db.query(Student)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .filter(Enrollment.class_id == c.id, Enrollment.valid_to.is_(None))
            .order_by(Student.admission_no)
            .all()
        )
        out_classes.append(
            {
                "id": c.id,
                "name": c.name,
                "academic_year": c.academic_year,
                "students": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "gender": s.gender,
                        "admission_no": s.admission_no,
                    }
                    for s in students
                ],
            }
        )
    stats = {
        "home_visits": (
            db.query(StudentEvent)
            .filter(StudentEvent.actor_teacher_id == teacher.id,
                    StudentEvent.event_type == "home_visited")
            .count()
        ),
        "results_entered": db.query(ExamResult).filter(ExamResult.entered_by == teacher.id).count(),
        "notes_added": (
            db.query(StudentEvent)
            .filter(StudentEvent.actor_teacher_id == teacher.id,
                    StudentEvent.event_type == "note_added")
            .count()
        ),
    }
    return {"teacher": teacher_out(teacher), "classes": out_classes, "stats": stats}


@router.patch("/profile")
def update_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    teacher.name = body.name.strip()
    teacher.email = (body.email or "").strip() or None
    teacher.subject = (body.subject or "").strip() or None
    db.commit()
    return teacher_out(teacher)
