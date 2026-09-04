from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..events import MANUAL_EVENT_TYPES, RECORD_EVENT_TYPES, SYSTEM_EVENT_TYPES, add_event, next_birthday_date
from ..models import (
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    Student,
    StudentEvent,
    User,
    utcnow,
)

router = APIRouter(tags=["students"])


def current_class(db: Session, student_id: int) -> Class | None:
    return (
        db.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(
            Enrollment.student_id == student_id,
            Enrollment.valid_to.is_(None),
        )
        .first()
    )


def last_exam_summary(db: Session, student_id: int) -> dict | None:
    """The student's most recent graded exam: name + per-subject scores."""
    latest = (
        db.query(Exam.id, Exam.name, Exam.exam_date)
        .join(ExamSubject, ExamSubject.exam_id == Exam.id)
        .join(ExamResult, ExamResult.exam_subject_id == ExamSubject.id)
        .filter(
            ExamResult.student_id == student_id,
            ExamResult.status == "entered",
            ExamResult.score.isnot(None),
        )
        .order_by(Exam.exam_date.desc(), Exam.id.desc())
        .first()
    )
    if latest is None:
        return None
    rows = (
        db.query(ExamSubject.subject, ExamResult.score)
        .join(ExamResult, ExamResult.exam_subject_id == ExamSubject.id)
        .filter(
            ExamSubject.exam_id == latest.id,
            ExamResult.student_id == student_id,
            ExamResult.status == "entered",
        )
        .all()
    )
    return {
        "exam_id": latest.id,
        "exam_name": latest.name,
        "exam_date": latest.exam_date.isoformat() if latest.exam_date else None,
        "scores": {subject: score for subject, score in rows},
    }


@router.get("/students")
def list_students(db: Session = Depends(get_db)):
    students = db.query(Student).order_by(Student.admission_no).all()
    out = []
    for s in students:
        cls = current_class(db, s.id)
        out.append(
            {
                "id": s.id,
                "admission_no": s.admission_no,
                "name": s.name,
                "gender": s.gender,
                "status": s.status,
                "class": {"id": cls.id, "name": cls.name} if cls else None,
                "last_exam": last_exam_summary(db, s.id),
            }
        )
    return out


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    gender: str | None = None
    birth_date: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    class_id: int


@router.post("/students", status_code=201)
def create_student(
    body: StudentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cls = db.get(Class, body.class_id)
    if cls is None:
        raise HTTPException(status_code=400, detail="class not found")
    max_no = 0
    for (no,) in db.query(Student.admission_no).all():
        digits = "".join(ch for ch in no if ch.isdigit())
        if digits.isdigit():
            max_no = max(max_no, int(digits))
    student = Student(
        admission_no=f"S{max_no + 1}",
        name=body.name.strip(),
        gender=body.gender or None,
        birth_date=body.birth_date,
        guardian_name=body.guardian_name or None,
        guardian_phone=body.guardian_phone.strip() if body.guardian_phone else None,
        address=body.address or None,
    )
    db.add(student)
    db.flush()
    db.add(Enrollment(student_id=student.id, class_id=cls.id,
                      valid_from=date.today(), reason="admitted"))
    add_event(db, student.id, "enrolled", utcnow(), actor_teacher_id=user.id,
              payload={"class": cls.name})
    if body.birth_date:
        # recurring birthday event so class/home pages can surface it
        bday = next_birthday_date(body.birth_date)
        add_event(db, student.id, "birthday",
                  datetime.combine(bday, time(9, 0)),
                  recurrence="yearly",
                  payload={"birth_date": body.birth_date.isoformat()})
    db.commit()
    return {"id": student.id, "admission_no": student.admission_no, "name": student.name}


@router.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="student not found")
    cls = current_class(db, s.id)
    results = (
        db.query(ExamResult, ExamSubject, Exam)
        .join(ExamSubject, ExamSubject.id == ExamResult.exam_subject_id)
        .join(Exam, Exam.id == ExamSubject.exam_id)
        .filter(ExamResult.student_id == student_id)
        .order_by(Exam.exam_date, ExamSubject.subject)
        .all()
    )
    return {
        "id": s.id,
        "admission_no": s.admission_no,
        "name": s.name,
        "gender": s.gender,
        "birth_date": s.birth_date.isoformat() if s.birth_date else None,
        "guardian_name": s.guardian_name,
        "guardian_phone": s.guardian_phone,
        "address": s.address,
        "status": s.status,
        "class": {"id": cls.id, "name": cls.name} if cls else None,
        "scores": [
            {
                "result_id": r.id,
                "exam_id": e.id,
                "exam_name": e.name,
                "exam_date": e.exam_date.isoformat(),
                "subject": es.subject,
                "score": r.score,
                "full_score": es.full_score,
                "status": r.status,
            }
            for r, es, e in results
        ],
    }


@router.get("/students/{student_id}/timeline")
def student_timeline(student_id: int, db: Session = Depends(get_db)):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(StudentEvent, User.name)
        .outerjoin(User, User.id == StudentEvent.actor_teacher_id)
        .filter(StudentEvent.student_id == student_id)
        .order_by(StudentEvent.occurred_at.desc(), StudentEvent.id.desc())
        .all()
    )
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "actor": actor,
            "payload": event.payload or {},
            "actor_teacher_id": event.actor_teacher_id,
            "is_system": event.event_type in SYSTEM_EVENT_TYPES,
        }
        for event, actor in rows
    ]


class EventRecordIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=2000)
    purpose: str | None = None
    follow_up_needed: bool = False
    follow_up_note: str | None = None
    occurred_at: datetime | None = None


# event types that are auto-generated by the system; the rest are teacher-defined
# (definitions live in app.events so dashboard/profile share the same sets)


@router.post("/students/{student_id}/events", status_code=201)
def create_event_record(
    student_id: int,
    body: EventRecordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    now = body.occurred_at or utcnow()
    # auto-classify: if not a known manual type, treat as custom
    is_custom = body.event_type not in MANUAL_EVENT_TYPES
    event = add_event(
        db,
        student_id,
        body.event_type,
        now,
        actor_teacher_id=user.id,
        payload={
            "summary": body.summary,
            "purpose": body.purpose,
            "follow_up_needed": body.follow_up_needed,
            "follow_up_note": body.follow_up_note,
            "is_custom": is_custom,
        },
    )
    db.commit()
    return {"id": event.id, "status": "created"}


@router.get("/students/{student_id}/events")
def list_student_events(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(StudentEvent, User.name)
        .outerjoin(User, User.id == StudentEvent.actor_teacher_id)
        .filter(
            StudentEvent.student_id == student_id,
            StudentEvent.actor_teacher_id.isnot(None),
            StudentEvent.event_type.notin_(list(SYSTEM_EVENT_TYPES)),
        )
        .order_by(StudentEvent.occurred_at.desc(), StudentEvent.id.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "occurred_at": e.occurred_at.isoformat(),
            "actor": actor,
            "payload": e.payload or {},
        }
        for e, actor in rows
    ]


@router.get("/records")
def list_records(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """跟进记录: every teacher-written StudentEvent school-wide, newest first."""
    rows = (
        db.query(StudentEvent, Student.name, User.name)
        .join(Student, Student.id == StudentEvent.student_id)
        .outerjoin(User, User.id == StudentEvent.actor_teacher_id)
        .filter(StudentEvent.event_type.in_(RECORD_EVENT_TYPES))
        .order_by(StudentEvent.occurred_at.desc(), StudentEvent.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": ev.id,
            "student_id": ev.student_id,
            "student_name": student_name,
            "event_type": ev.event_type,
            "occurred_at": ev.occurred_at.isoformat(),
            "actor": actor,
            "payload": ev.payload or {},
        }
        for ev, student_name, actor in rows
    ]


@router.get("/teachers/me/event-types")
def my_event_types(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the teacher's recently used custom event types (distinct, recent top N)."""
    rows = (
        db.query(StudentEvent.event_type)
        .filter(
            StudentEvent.actor_teacher_id == user.id,
            StudentEvent.event_type.notin_(list(SYSTEM_EVENT_TYPES)),
            StudentEvent.event_type.notin_(list(MANUAL_EVENT_TYPES)),
        )
        .distinct()
        .order_by(StudentEvent.event_type)
        .all()
    )
    return [r[0] for r in rows]


def _event_to_dict(e: StudentEvent, actor: str | None = None) -> dict:
    return {
        "id": e.id,
        "event_type": e.event_type,
        "occurred_at": e.occurred_at.isoformat(),
        "actor": actor,
        "payload": e.payload or {},
        "actor_teacher_id": e.actor_teacher_id,
        "is_system": e.event_type in SYSTEM_EVENT_TYPES,
    }


@router.get("/students/{student_id}/events/{event_id}")
def get_event(
    student_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(StudentEvent, User.name)
        .outerjoin(User, User.id == StudentEvent.actor_teacher_id)
        .filter(StudentEvent.id == event_id, StudentEvent.student_id == student_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    return _event_to_dict(row[0], row[1])


@router.patch("/students/{student_id}/events/{event_id}")
def update_event(
    student_id: int,
    event_id: int,
    body: EventRecordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ev = db.get(StudentEvent, event_id)
    if ev is None or ev.student_id != student_id:
        raise HTTPException(status_code=404, detail="event not found")
    if ev.event_type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be modified")
    if ev.actor_teacher_id is not None and ev.actor_teacher_id != user.id:
        raise HTTPException(status_code=403, detail="cannot edit another teacher's event")
    ev.event_type = body.event_type
    ev.occurred_at = body.occurred_at or ev.occurred_at
    ev.payload = {
        "summary": body.summary,
        "purpose": body.purpose,
        "follow_up_needed": body.follow_up_needed,
        "follow_up_note": body.follow_up_note,
        "is_custom": body.event_type not in MANUAL_EVENT_TYPES,
    }
    db.commit()
    db.refresh(ev)
    return {"id": ev.id, "status": "updated"}


@router.delete("/students/{student_id}/events/{event_id}")
def delete_event(
    student_id: int,
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ev = db.get(StudentEvent, event_id)
    if ev is None or ev.student_id != student_id:
        raise HTTPException(status_code=404, detail="event not found")
    if ev.event_type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be deleted")
    if ev.actor_teacher_id is not None and ev.actor_teacher_id != user.id:
        raise HTTPException(status_code=403, detail="cannot delete another teacher's event")
    db.delete(ev)
    db.commit()
    return {"status": "deleted"}


class ScoreUpdateIn(BaseModel):
    score: float
    reason: str | None = None


@router.patch("/results/{result_id}")
def update_result(
    result_id: int,
    body: ScoreUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = db.get(ExamResult, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="result not found")
    es = db.get(ExamSubject, result.exam_subject_id)
    exam = db.get(Exam, es.exam_id)
    if body.score < 0 or body.score > es.full_score:
        raise HTTPException(status_code=400, detail="score out of range")
    old = result.score
    if old is not None and abs(body.score - old) < 0.01:
        return {"id": result.id, "score": result.score, "changed": False}

    result.score = body.score
    result.updated_at = utcnow()
    result.entered_by = user.id
    add_event(
        db,
        result.student_id,
        "result_changed",
        utcnow(),
        actor_teacher_id=user.id,
        ref_table="exam_result",
        ref_id=result.id,
        payload={
            "exam": exam.name,
            "subject": es.subject,
            "old": old,
            "new": body.score,
            "reason": body.reason,
        },
    )
    db.commit()
    return {"id": result.id, "score": result.score, "changed": True}


class StudentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    gender: str | None = None
    birth_date: date | None = None
    guardian_name: str | None = None
    guardian_phone: str | None = Field(default=None, min_length=5, max_length=40)
    address: str | None = None
    status: str | None = None  # active | inactive
    class_id: int | None = None  # omit to leave class unchanged


@router.patch("/students/{student_id}")
def update_student(
    student_id: int,
    body: StudentUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="student not found")

    if body.name is not None:
        s.name = body.name.strip()
    if body.gender is not None:
        s.gender = body.gender or None
    if body.birth_date is not None:
        s.birth_date = body.birth_date
    if body.guardian_name is not None:
        s.guardian_name = body.guardian_name or None
    if body.guardian_phone is not None:
        s.guardian_phone = body.guardian_phone.strip()
    if body.address is not None:
        s.address = body.address or None
    if body.status is not None:
        if body.status not in ("active", "inactive"):
            raise HTTPException(status_code=400, detail="status must be 'active' or 'inactive'")
        s.status = body.status

    # Class change: close current enrollment, open a new one, record event.
    if body.class_id is not None:
        new_cls = db.get(Class, body.class_id)
        if new_cls is None:
            raise HTTPException(status_code=400, detail="class not found")
        current = current_class(db, s.id)
        if current is None or current.id != body.class_id:
            old_enrollment = (
                db.query(Enrollment)
                .filter(Enrollment.student_id == student_id, Enrollment.valid_to.is_(None))
                .first()
            )
            old_name = current.name if current else None
            if old_enrollment is not None:
                old_enrollment.valid_to = date.today()
            db.add(
                Enrollment(
                    student_id=student_id,
                    class_id=new_cls.id,
                    valid_from=date.today(),
                    reason="moved",
                )
            )
            if old_name is not None:
                add_event(
                    db,
                    student_id,
                    "class_moved",
                    utcnow(),
                    actor_teacher_id=user.id,
                    payload={"from": old_name, "to": new_cls.name},
                )

    db.commit()
    cls = current_class(db, s.id)
    return {
        "id": s.id,
        "admission_no": s.admission_no,
        "name": s.name,
        "gender": s.gender,
        "status": s.status,
        "class": {"id": cls.id, "name": cls.name} if cls else None,
    }


@router.delete("/students/{student_id}")
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="student not found")
    # Only allow hard delete when the student has no written evidence so the
    # data integrity stays intact. Otherwise move to "inactive".
    # Remaining evidence: ExamResult rows and any teacher-written StudentEvent
    # (the generic 跟进记录 — home visits, talks, calls, tutoring, notes).
    has_results = db.query(ExamResult).filter(ExamResult.student_id == student_id).first() is not None
    has_records = (
        db.query(StudentEvent)
        .filter(StudentEvent.student_id == student_id,
                StudentEvent.event_type.in_(MANUAL_EVENT_TYPES))
        .first() is not None
    )
    if has_results or has_records:
        # Soft delete: move status to inactive + close enrollments
        s.status = "inactive"
        for e in db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.valid_to.is_(None)).all():
            e.valid_to = date.today()
        add_event(db, student_id, "note_added", utcnow(), actor_teacher_id=user.id,
                  payload={"note": "账号停用"})
        db.commit()
        return {"ok": True, "action": "deactivated"}

    db.query(StudentEvent).filter(StudentEvent.student_id == student_id).delete()
    db.query(Enrollment).filter(Enrollment.student_id == student_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True, "action": "deleted"}
