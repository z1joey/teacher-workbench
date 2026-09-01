from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Teacher

router = APIRouter(tags=["teachers"])


@router.get("/teachers")
def list_teachers(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).order_by(Teacher.id).all()
    return [
        {"id": t.id, "name": t.name, "subject": t.subject, "email": t.email}
        for t in teachers
    ]
