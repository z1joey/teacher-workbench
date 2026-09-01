from datetime import date

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
    guardian_phone: str = Field(min_length=5, max_length=40)
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
        guardian_phone=body.guardian_phone.strip(),
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


class HomeVisitIn(BaseModel):
    purpose: str | None = None
    summary: str
    follow_up_needed: bool = False
    follow_up_note: str | None = None


@router.post("/students/{student_id}/home-visits", status_code=201)
def create_home_visit(
    student_id: int,
    body: HomeVisitIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    if db.get(Student, student_id) is None:
        raise HTTPException(status_code=404, detail="student not found")
    visit = HomeVisit(
        student_id=student_id,
        teacher_id=teacher.id,
        visited_at=utcnow(),
        purpose=body.purpose,
        summary=body.summary,
        follow_up_needed=body.follow_up_needed,
        follow_up_note=body.follow_up_note,
    )
    db.add(visit)
    db.flush()  # assign visit.id before referencing it in the event
    add_event(
        db,
        student_id,
        "home_visited",
        visit.visited_at,
        actor_teacher_id=teacher.id,
        ref_table="home_visit",
        ref_id=visit.id,
        payload={
            "purpose": body.purpose,
            "summary": body.summary,
            "follow_up_needed": body.follow_up_needed,
        },
    )
    db.commit()
    return {"id": visit.id, "status": "created"}


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
