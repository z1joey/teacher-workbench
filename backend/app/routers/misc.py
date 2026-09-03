from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TeacherProfile, User

router = APIRouter(tags=["teachers"])


@router.get("/teachers")
def list_teachers(db: Session = Depends(get_db)):
    """Teacher-role users — drives homeroom-teacher dropdowns."""
    rows = (
        db.query(User, TeacherProfile.subject)
        .outerjoin(TeacherProfile, TeacherProfile.user_id == User.id)
        .filter(User.role == "teacher")
        .order_by(User.id)
        .all()
    )
    return [
        {"id": u.id, "name": u.name, "subject": subject, "email": u.email}
        for u, subject in rows
    ]
