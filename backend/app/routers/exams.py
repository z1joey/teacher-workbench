from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..models import (
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    Teacher,
)

router = APIRouter(tags=["exams"])


class SubjectIn(BaseModel):
    subject: str = Field(min_length=1, max_length=50)
    full_score: float = Field(gt=0, le=1000)


class ExamIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    exam_date: date
    term: str | None = None
    exam_type: str = Field(default="midterm", max_length=30)
    academic_year: str | None = None
    subjects: list[SubjectIn] = Field(min_length=1)


@router.post("/exams", status_code=201)
def create_exam(
    body: ExamIn,
    db: Session = Depends(get_db),
    teacher: Teacher = Depends(get_current_teacher),
):
    exam_date = body.exam_date
    if body.academic_year:
        academic_year = body.academic_year.strip()
    else:
        start = exam_date.year if exam_date.month >= 8 else exam_date.year - 1
        academic_year = f"{start}/{start + 1}"
    if (
        db.query(Exam)
        .filter(Exam.name == body.name.strip(), Exam.academic_year == academic_year)
        .first()
        is not None
    ):
        raise HTTPException(status_code=409, detail="该学年已存在同名考试")
    exam = Exam(
        name=body.name.strip(),
        academic_year=academic_year,
        term=body.term,
        exam_date=exam_date,
        exam_type=body.exam_type,
    )
    db.add(exam)
    db.flush()
    for s in body.subjects:
        db.add(ExamSubject(exam_id=exam.id, subject=s.subject.strip(), full_score=s.full_score))
    db.commit()
    return {"id": exam.id, "name": exam.name, "academic_year": academic_year}


@router.get("/exams")
def list_exams(db: Session = Depends(get_db)):
    exams = db.query(Exam).order_by(Exam.exam_date.desc()).all()
    out = []
    for e in exams:
        subjects = (
            db.query(ExamSubject)
            .filter(ExamSubject.exam_id == e.id)
            .order_by(ExamSubject.subject)
            .all()
        )
        out.append(
            {
                "id": e.id,
                "name": e.name,
                "academic_year": e.academic_year,
                "term": e.term,
                "exam_date": e.exam_date.isoformat(),
                "exam_type": e.exam_type,
                "subjects": [
                    {"id": s.id, "subject": s.subject, "full_score": s.full_score}
                    for s in subjects
                ],
            }
        )
    return out


@router.get("/exams/trend")
def exams_trend(db: Session = Depends(get_db), teacher: Teacher = Depends(get_current_teacher)):
    # NOTE: declared before /exams/{exam_id} so "trend" is not captured as an id.
    exams = db.query(Exam).order_by(Exam.exam_date, Exam.id).all()
    index_of = {e.id: i for i, e in enumerate(exams)}
    rows = (
        db.query(
            ExamSubject.exam_id,
            ExamSubject.subject,
            ExamSubject.full_score,
            func.avg(ExamResult.score),
        )
        .join(ExamResult, ExamResult.exam_subject_id == ExamSubject.id)
        .filter(ExamResult.status == "entered")
        .group_by(ExamSubject.exam_id, ExamSubject.subject, ExamSubject.full_score)
        .all()
    )
    per_subject: dict[str, dict] = {}
    for exam_id, subject, full_score, avg in rows:
        rec = per_subject.setdefault(subject, {"full_score": 0.0, "values": [None] * len(exams)})
        rec["full_score"] = max(rec["full_score"], full_score or 0)
        if exam_id in index_of and avg is not None:
            rec["values"][index_of[exam_id]] = round(float(avg), 1)
    return {
        "exams": [
            {
                "id": e.id,
                "name": e.name,
                "exam_date": e.exam_date.isoformat(),
            }
            for e in exams
        ],
        "series": [
            {"subject": subject, "values": rec["values"], "full_score": rec["full_score"]}
            for subject, rec in sorted(per_subject.items())
        ],
    }


@router.get("/exams/{exam_id}")
def get_exam(exam_id: int, db: Session = Depends(get_db)):
    e = db.get(Exam, exam_id)
    if e is None:
        raise HTTPException(status_code=404, detail="exam not found")
    subjects = (
        db.query(ExamSubject)
        .filter(ExamSubject.exam_id == e.id)
        .order_by(ExamSubject.subject)
        .all()
    )
    return {
        "id": e.id,
        "name": e.name,
        "academic_year": e.academic_year,
        "term": e.term,
        "exam_date": e.exam_date.isoformat(),
        "exam_type": e.exam_type,
        "subjects": [
            {"id": s.id, "subject": s.subject, "full_score": s.full_score} for s in subjects
        ],
    }


@router.get("/exams/{exam_id}/averages")
def exam_averages(exam_id: int, db: Session = Depends(get_db)):
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="exam not found")

    # School-wide average per subject (entered results only, absent excluded)
    school_rows = (
        db.query(
            ExamSubject.subject,
            ExamSubject.full_score,
            func.avg(ExamResult.score),
            func.min(ExamResult.score),
            func.max(ExamResult.score),
            func.count(ExamResult.id),
        )
        .join(ExamResult, ExamResult.exam_subject_id == ExamSubject.id)
        .filter(ExamSubject.exam_id == exam_id, ExamResult.status == "entered")
        .group_by(ExamSubject.id)
        .order_by(ExamSubject.subject)
        .all()
    )

    # Per-class average. Class attribution uses the roster *as of the exam
    # date* via the temporal enrollment table, so a student who moved class
    # is counted in the class they belonged to on exam day.
    class_rows = (
        db.query(
            Class.id,
            Class.name,
            ExamSubject.subject,
            func.avg(ExamResult.score),
            func.count(ExamResult.id),
        )
        .select_from(ExamResult)
        .join(ExamSubject, ExamSubject.id == ExamResult.exam_subject_id)
        .join(Exam, Exam.id == ExamSubject.exam_id)
        .join(
            Enrollment,
            and_(
                Enrollment.student_id == ExamResult.student_id,
                Enrollment.valid_from <= Exam.exam_date,
                or_(Enrollment.valid_to.is_(None), Enrollment.valid_to >= Exam.exam_date),
            ),
        )
        .join(Class, Class.id == Enrollment.class_id)
        .filter(ExamSubject.exam_id == exam_id, ExamResult.status == "entered")
        .group_by(Class.id, Class.name, ExamSubject.subject)
        .order_by(Class.name, ExamSubject.subject)
        .all()
    )

    return {
        "exam": {
            "id": exam.id,
            "name": exam.name,
            "exam_date": exam.exam_date.isoformat(),
            "term": exam.term,
            "exam_type": exam.exam_type,
        },
        "school": [
            {
                "subject": subject,
                "full_score": full,
                "avg": round(float(avg), 1) if avg is not None else None,
                "min": round(float(min_), 1) if min_ is not None else None,
                "max": round(float(max_), 1) if max_ is not None else None,
                "count": count,
            }
            for subject, full, avg, min_, max_, count in school_rows
        ],
        "classes": [
            {
                "class_id": class_id,
                "class_name": class_name,
                "subject": subject,
                "avg": round(float(avg), 1) if avg is not None else None,
                "count": count,
            }
            for class_id, class_name, subject, avg, count in class_rows
        ],
    }
