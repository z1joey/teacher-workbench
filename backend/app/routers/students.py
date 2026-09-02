from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..events import add_event
from ..models import (
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    HomeVisit,
    KnowledgePoint,
    Question,
    QuestionResponse,
    Student,
    StudentEvent,
    StudentWeakness,
    Teacher,
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
    teacher: Teacher = Depends(get_current_teacher),
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
    add_event(db, student.id, "enrolled", utcnow(), actor_teacher_id=teacher.id,
              payload={"class": cls.name})
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
    visits = (
        db.query(HomeVisit)
        .filter(HomeVisit.student_id == student_id)
        .order_by(HomeVisit.visited_at.desc())
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
        "home_visits": [
            {
                "id": v.id,
                "visited_at": v.visited_at.isoformat(),
                "purpose": v.purpose,
                "summary": v.summary,
                "follow_up_needed": v.follow_up_needed,
                "follow_up_note": v.follow_up_note,
            }
            for v in visits
        ],
    }


@router.get("/students/{student_id}/timeline")
def student_timeline(student_id: int, db: Session = Depends(get_db)):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(StudentEvent, Teacher.name)
        .outerjoin(Teacher, Teacher.id == StudentEvent.actor_teacher_id)
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


@router.get("/students/{student_id}/weaknesses")
def student_weaknesses(student_id: int, db: Session = Depends(get_db)):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(StudentWeakness, KnowledgePoint)
        .join(KnowledgePoint, KnowledgePoint.id == StudentWeakness.knowledge_point_id)
        .filter(StudentWeakness.student_id == student_id)
        .order_by(StudentWeakness.status, StudentWeakness.severity.desc())
        .all()
    )
    return [
        {
            "id": w.id,
            "subject": kp.subject,
            "knowledge_point": kp.name,
            "evidence_count": w.evidence_count,
            "attempts": w.attempts,
            "severity": round(w.severity, 2),
            "status": w.status,
            "first_seen": w.first_seen.isoformat(),
            "last_seen": w.last_seen.isoformat(),
        }
        for w, kp in rows
    ]


@router.get("/students/{student_id}/failed-questions")
def failed_questions(student_id: int, subject: str | None = None, db: Session = Depends(get_db)):
    query = (
        db.query(QuestionResponse, Question, KnowledgePoint, ExamSubject, Exam)
        .join(Question, Question.id == QuestionResponse.question_id)
        .outerjoin(KnowledgePoint, KnowledgePoint.id == Question.knowledge_point_id)
        .join(ExamSubject, ExamSubject.id == Question.exam_subject_id)
        .join(Exam, Exam.id == ExamSubject.exam_id)
        .filter(
            QuestionResponse.student_id == student_id,
            QuestionResponse.is_correct.is_(False),
        )
        .order_by(Exam.exam_date.desc(), ExamSubject.subject, Question.question_no)
    )
    if subject is not None:
        query = query.filter(ExamSubject.subject == subject)
    rows = query.all()
    return [
        {
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat(),
            "subject": es.subject,
            "question_no": q.question_no,
            "question_type": q.question_type,
            "topic": kp.name if kp else None,
            "earned": qr.earned,
            "max_score": q.max_score,
        }
        for qr, q, kp, es, exam in rows
    ]


class EventRecordIn(BaseModel):
    event_type: str = Field(min_length=1, max_length=40)
    summary: str = Field(min_length=1, max_length=2000)
    purpose: str | None = None
    follow_up_needed: bool = False
    follow_up_note: str | None = None
    occurred_at: datetime | None = None


# event types that are auto-generated by the system; the rest are teacher-defined
SYSTEM_EVENT_TYPES = {
    "enrolled", "class_moved", "exam_taken", "result_changed", "weakness_flagged",
}

# event types that teacher defines manually; rest are system-generated
MANUAL_EVENT_TYPES = {
    "home_visited", "talk", "tutoring", "parent_call", "note_added",
}


@router.post("/students/{student_id}/events", status_code=201)
def create_event_record(
    student_id: int,
    body: EventRecordIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
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
        actor_teacher_id=teacher.id,
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
    teacher: Teacher = Depends(get_current_teacher),
):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    rows = (
        db.query(StudentEvent, Teacher.name)
        .outerjoin(Teacher, Teacher.id == StudentEvent.actor_teacher_id)
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


@router.get("/teachers/me/event-types")
def my_event_types(
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    """Return the teacher's recently used custom event types (distinct, recent top N)."""
    rows = (
        db.query(StudentEvent.event_type)
        .filter(
            StudentEvent.actor_teacher_id == teacher.id,
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
    teacher: Teacher = Depends(get_current_teacher),
):
    row = (
        db.query(StudentEvent, Teacher.name)
        .outerjoin(Teacher, Teacher.id == StudentEvent.actor_teacher_id)
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
    teacher: Teacher = Depends(get_current_teacher),
):
    ev = db.get(StudentEvent, event_id)
    if ev is None or ev.student_id != student_id:
        raise HTTPException(status_code=404, detail="event not found")
    if ev.event_type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be modified")
    if ev.actor_teacher_id is not None and ev.actor_teacher_id != teacher.id:
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
    teacher: Teacher = Depends(get_current_teacher),
):
    ev = db.get(StudentEvent, event_id)
    if ev is None or ev.student_id != student_id:
        raise HTTPException(status_code=404, detail="event not found")
    if ev.event_type in SYSTEM_EVENT_TYPES:
        raise HTTPException(status_code=400, detail="system events cannot be deleted")
    if ev.actor_teacher_id is not None and ev.actor_teacher_id != teacher.id:
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
    teacher: Teacher = Depends(get_current_teacher),
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
    result.entered_by = teacher.id
    add_event(
        db,
        result.student_id,
        "result_changed",
        utcnow(),
        actor_teacher_id=teacher.id,
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
    teacher: Teacher = Depends(get_current_teacher),
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
                    actor_teacher_id=teacher.id,
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
    teacher: Teacher = Depends(get_current_teacher),
):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="student not found")
    # Only allow hard delete when the student has no written evidence so the
    # data integrity stays intact. Otherwise move to "inactive".
    has_results = db.query(ExamResult).filter(ExamResult.student_id == student_id).first() is not None
    has_responses = db.query(QuestionResponse).filter(QuestionResponse.student_id == student_id).first() is not None
    has_weaknesses = db.query(StudentWeakness).filter(StudentWeakness.student_id == student_id).first() is not None
    has_visits = db.query(HomeVisit).filter(HomeVisit.student_id == student_id).first() is not None
    if has_results or has_responses or has_weaknesses or has_visits:
        # Soft delete: move status to inactive + close enrollments
        s.status = "inactive"
        for e in db.query(Enrollment).filter(Enrollment.student_id == student_id, Enrollment.valid_to.is_(None)).all():
            e.valid_to = date.today()
        add_event(db, student_id, "note_added", utcnow(), actor_teacher_id=teacher.id,
                  payload={"note": "账号停用"})
        db.commit()
        return {"ok": True, "action": "deactivated"}

    db.query(StudentEvent).filter(StudentEvent.student_id == student_id).delete()
    db.query(Enrollment).filter(Enrollment.student_id == student_id).delete()
    db.delete(s)
    db.commit()
    return {"ok": True, "action": "deleted"}
