from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..events import MANUAL_EVENT_TYPES
from ..models import Class, Enrollment, ExamResult, Student, StudentEvent, TeacherProfile, User

router = APIRouter(tags=["profile"])


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "phone": u.phone,
        "email": u.email,
        "subject": u.profile.subject if u.profile else None,
        "role": u.role,
    }


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None
    subject: str | None = None


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    classes = (
        db.query(Class)
        .filter(Class.homeroom_teacher_id == user.id)
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
        "interactions": (
            db.query(StudentEvent)
            .filter(StudentEvent.actor_teacher_id == user.id,
                    StudentEvent.event_type.in_(MANUAL_EVENT_TYPES))
            .count()
        ),
        "results_entered": db.query(ExamResult).filter(ExamResult.entered_by == user.id).count(),
        "notes_added": (
            db.query(StudentEvent)
            .filter(StudentEvent.actor_teacher_id == user.id,
                    StudentEvent.event_type == "note_added")
            .count()
        ),
    }
    return {"user": user_out(user), "classes": out_classes, "stats": stats}


@router.patch("/profile")
def update_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.name = body.name.strip()
    user.email = (body.email or "").strip() or None
    if user.role == "teacher":
        if user.profile is None:
            user.profile = TeacherProfile(subject=(body.subject or "").strip() or None)
        else:
            user.profile.subject = (body.subject or "").strip() or None
    db.commit()
    return user_out(user)
