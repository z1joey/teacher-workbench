"""Per-teacher workspace isolation.

Each teacher owns a workspace_id. Students and owned classes belong to that
workspace so a newly registered account starts empty instead of inheriting
another teacher's roster or events.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Class, Person
from .payloads import validate_person_payload
from .unassigned import is_unassigned_class


def ensure_workspace_id(teacher: Person) -> str:
    payload = dict(teacher.payload or {})
    wid = payload.get("workspace_id")
    if not wid:
        wid = str(uuid.uuid4())
        payload["workspace_id"] = wid
        teacher.payload = validate_person_payload("teacher", payload)
    return wid


def workspace_id(teacher: Person) -> str:
    wid = (teacher.payload or {}).get("workspace_id")
    if not wid:
        return ensure_workspace_id(teacher)
    return wid


def tag_student_workspace(student: Person, teacher: Person) -> None:
    payload = dict(student.payload or {})
    payload["workspace_id"] = workspace_id(teacher)
    student.payload = validate_person_payload("student", payload)


def students_query(db: Session, teacher: Person):
    wid = workspace_id(teacher)
    return db.query(Person).filter(
        Person.payload["role"].as_string() == "student",
        Person.payload["workspace_id"].as_string() == wid,
    )


def classes_query(db: Session, teacher: Person):
    return db.query(Class).filter(Class.teacher_id == teacher.id)


def student_in_workspace(student: Person | None, teacher: Person) -> bool:
    if student is None or student.role != "student":
        return False
    return (student.payload or {}).get("workspace_id") == workspace_id(teacher)


def require_student_in_workspace(
    db: Session, teacher: Person, student_id: uuid.UUID
) -> Person:
    student = db.get(Person, student_id)
    if not student_in_workspace(student, teacher):
        raise HTTPException(status_code=404, detail="student not found")
    return student


def require_class_in_workspace(
    db: Session, teacher: Person, class_id: uuid.UUID
) -> Class:
    cls = db.get(Class, class_id)
    if cls is None or is_unassigned_class(cls) or cls.teacher_id != teacher.id:
        raise HTTPException(status_code=404, detail="class not found")
    return cls


def migrate_legacy_workspace(db: Session) -> None:
    """Assign orphan rows from before workspace isolation to the first teacher."""
    role = Person.payload["role"].as_string()
    teachers = (
        db.query(Person)
        .filter(role == "teacher")
        .order_by(Person.created_at.asc(), Person.id.asc())
        .all()
    )
    if not teachers:
        return
    owner = teachers[0]
    ensure_workspace_id(owner)
    db.flush()
    for student in db.query(Person).filter(role == "student").all():
        if (student.payload or {}).get("workspace_id"):
            continue
        tag_student_workspace(student, owner)
    for cls in db.query(Class).all():
        if is_unassigned_class(cls) or cls.teacher_id is not None:
            continue
        cls.teacher_id = owner.id
