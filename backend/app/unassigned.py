"""The system-wide placeholder class for students not yet assigned."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Class

UNASSIGNED_CLASS_NAME = "未分班"
UNASSIGNED_ACADEMIC_YEAR = "__system__"


def is_unassigned_class(cls: Class | None) -> bool:
    if cls is None:
        return False
    return (
        cls.name == UNASSIGNED_CLASS_NAME
        and cls.academic_year == UNASSIGNED_ACADEMIC_YEAR
    )


def ensure_unassigned_class(db: Session) -> Class:
    """Return the singleton unassigned class, creating it if missing."""
    cls = (
        db.query(Class)
        .filter(
            Class.name == UNASSIGNED_CLASS_NAME,
            Class.academic_year == UNASSIGNED_ACADEMIC_YEAR,
        )
        .first()
    )
    if cls is None:
        cls = Class(
            name=UNASSIGNED_CLASS_NAME,
            grade_level=0,
            academic_year=UNASSIGNED_ACADEMIC_YEAR,
        )
        db.add(cls)
        db.flush()
    return cls


def class_for_api(cls: Class | None) -> dict | None:
    """Hide the system unassigned class from teacher-facing class fields."""
    if cls is None or is_unassigned_class(cls):
        return None
    return {"id": str(cls.id), "name": cls.name}
