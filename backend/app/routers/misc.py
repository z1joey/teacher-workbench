from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Person

router = APIRouter(tags=["teachers"])


@router.get("/teachers")
def list_teachers(db: Session = Depends(get_db)):
    """Teacher-role persons — drives homeroom-teacher dropdowns."""
    rows = (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "teacher")
        .order_by(Person.id)
        .all()
    )
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "email": p.email,
        }
        for p in rows
    ]
