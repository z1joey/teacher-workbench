"""Per-teacher workspace isolation.

Each teacher owns a workspace_id. Students and owned classes belong to that
workspace so a newly registered account starts empty instead of inheriting
another teacher's roster or events.

Invariant: ids are minted only by ``ensure_workspace_id`` on write paths (the
caller commits). Reads never mutate — ``workspace_id`` returns "" when the
account has none, a value no stored row can carry, so every workspace filter
comes back empty instead of matching rows from a forked workspace.
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Class, Enrollment, Event, Person
from .models.associations import student_guardians
from .payloads import validate_person_payload
from .unassigned import is_unassigned_class


def ensure_workspace_id(teacher: Person) -> str:
    """Mint the workspace id if missing and attach it to the payload.

    Write-path only: the assignment persists when the caller commits.
    """
    payload = dict(teacher.payload or {})
    wid = payload.get("workspace_id")
    if not wid:
        wid = str(uuid.uuid4())
        payload["workspace_id"] = wid
        teacher.payload = validate_person_payload("teacher", payload)
    return wid


def workspace_id(teacher: Person) -> str:
    """Stored workspace id, or "" when the account has none yet.

    Read path — must never mint. Regenerating per request (the old behavior)
    left writes stable but reads on a fresh random id every request, so pages
    rendered empty while the account silently forked from its own data.
    """
    return (teacher.payload or {}).get("workspace_id") or ""


def tag_student_workspace(student: Person, teacher: Person) -> None:
    payload = dict(student.payload or {})
    payload["workspace_id"] = ensure_workspace_id(teacher)
    student.payload = validate_person_payload("student", payload)


def students_query(db: Session, teacher: Person):
    wid = workspace_id(teacher)
    return db.query(Person).filter(
        Person.payload["role"].as_string() == "student",
        Person.payload["workspace_id"].as_string() == wid,
    )


def classes_query(db: Session, teacher: Person, include_archived: bool = False):
    q = db.query(Class).filter(Class.teacher_id == teacher.id)
    if not include_archived:
        q = q.filter(Class.archived.is_(False))
    return q


def archived_class_students_query(db: Session, class_id: uuid.UUID):
    """Graduates of an archived class, ordered by 学号.

    Must not use SELECT DISTINCT on ``Person`` while ordering by a JSON
    extract. PostgreSQL requires ORDER BY expressions to appear in the
    select list, and ``payload->>'admission_no'`` is not a selected column
    of ``person.*``. Demo seed creates 六1班 as archived, so GET /profile
    hits this after load-demo.
    """
    return (
        db.query(Person)
        .join(Enrollment, Enrollment.person_id == Person.id)
        .filter(
            Enrollment.class_id == class_id,
            Person.payload["graduated_at"].as_string().is_not(None),
        )
        .order_by(Person.payload["admission_no"].as_string(), Person.id)
    )


def archived_class_students(db: Session, class_id: uuid.UUID) -> list[Person]:
    """Unique graduates of an archived class, ordered by 学号."""
    seen: set[uuid.UUID] = set()
    out: list[Person] = []
    for person in archived_class_students_query(db, class_id):
        if person.id in seen:
            continue
        seen.add(person.id)
        out.append(person)
    return out


def admission_no_taken(
    db: Session,
    admission_no: str,
    workspace_wid: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    """Return whether another student in the same workspace already uses this 学号."""
    q = db.query(Person.id).filter(
        Person.payload["role"].as_string() == "student",
        Person.payload["workspace_id"].as_string() == workspace_wid,
        Person.payload["admission_no"].as_string() == admission_no,
    )
    if exclude_id is not None:
        q = q.filter(Person.id != exclude_id)
    return q.first() is not None


def workspace_owner_label(teacher: Person | None) -> str | None:
    if teacher is None:
        return None
    name = (teacher.name or "").strip() or "未命名"
    if teacher.email:
        return f"{name} · {teacher.email}"
    if teacher.phone:
        return f"{name} · {teacher.phone}"
    return name


def build_workspace_admin_maps(db: Session):
    """Maps for admin listings: workspace_id -> teacher, guardian -> owner labels."""
    role_teacher = Person.payload["role"].as_string() == "teacher"
    teachers_by_wid: dict[str, Person] = {}
    for teacher in db.query(Person).filter(role_teacher).all():
        wid = (teacher.payload or {}).get("workspace_id")
        if wid:
            teachers_by_wid[wid] = teacher

    def label_for_wid(wid: str | None) -> str | None:
        if not wid:
            return None
        return workspace_owner_label(teachers_by_wid.get(wid))

    student_wids: dict[uuid.UUID, str] = {}
    role_student = Person.payload["role"].as_string() == "student"
    for student_id, payload in db.query(Person.id, Person.payload).filter(role_student).all():
        wid = (payload or {}).get("workspace_id")
        if wid:
            student_wids[student_id] = wid

    guardian_labels: dict[uuid.UUID, list[str]] = defaultdict(list)
    if student_wids:
        for guardian_id, student_id in db.query(
            student_guardians.c.guardian_id,
            student_guardians.c.student_id,
        ):
            wid = student_wids.get(student_id)
            if not wid:
                continue
            label = label_for_wid(wid)
            if label and label not in guardian_labels[guardian_id]:
                guardian_labels[guardian_id].append(label)

    return teachers_by_wid, label_for_wid, guardian_labels


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
    if cls is None:
        raise HTTPException(status_code=404, detail="class not found")
    if is_unassigned_class(cls):
        return cls
    if cls.teacher_id != teacher.id:
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
    wid = ensure_workspace_id(owner)
    db.flush()
    for student in db.query(Person).filter(role == "student").all():
        if (student.payload or {}).get("workspace_id"):
            continue
        tag_student_workspace(student, owner)
    for cls in db.query(Class).all():
        if is_unassigned_class(cls) or cls.teacher_id is not None:
            continue
        cls.teacher_id = owner.id
    # exam sittings + score rows predate workspace isolation: claim them for
    # the first teacher so other workspaces never see legacy exam data
    from .payloads import validate_event_payload

    for ev in (
        db.query(Event).filter(Event.type.in_(("exam", "score"))).all()
    ):
        payload = dict(ev.payload or {})
        if payload.get("workspace_id"):
            continue
        payload["workspace_id"] = wid
        ev.payload = validate_event_payload(ev.type, payload)
