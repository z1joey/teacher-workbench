from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_teacher
from ..models import Class, Enrollment, Exam, ExamResult, ExamSubject, Student, Teacher

router = APIRouter(tags=["classes"])


def class_out(c: Class, teacher: Teacher | None, students: list[Student]) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "grade_level": c.grade_level,
        "academic_year": c.academic_year,
        "homeroom_teacher_id": c.homeroom_teacher_id,
        "homeroom_teacher": teacher.name if teacher else None,
        "student_count": len(students),
        "students": [
            {"id": s.id, "name": s.name, "gender": s.gender, "admission_no": s.admission_no}
            for s in students
        ],
    }


def current_students(db: Session, class_id: int) -> list[Student]:
    return (
        db.query(Student)
        .join(Enrollment, Enrollment.student_id == Student.id)
        .filter(Enrollment.class_id == class_id, Enrollment.valid_to.is_(None))
        .order_by(Student.admission_no)
        .all()
    )


class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    grade_level: int = Field(ge=1, le=12)
    academic_year: str = Field(min_length=4, max_length=20)
    homeroom_teacher_id: int | None = None


def _validate_teacher(db: Session, teacher_id: int | None) -> None:
    if teacher_id is not None and db.get(Teacher, teacher_id) is None:
        raise HTTPException(status_code=400, detail="teacher not found")


def _check_duplicate(db: Session, name: str, academic_year: str, exclude_id: int | None = None) -> None:
    query = db.query(Class).filter(Class.name == name, Class.academic_year == academic_year)
    if exclude_id is not None:
        query = query.filter(Class.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail="该学年已存在同名班级")


@router.get("/classes")
def list_classes(db: Session = Depends(get_db)):
    out = []
    for c in db.query(Class).order_by(Class.grade_level, Class.name).all():
        teacher = db.get(Teacher, c.homeroom_teacher_id) if c.homeroom_teacher_id else None
        out.append(class_out(c, teacher, current_students(db, c.id)))
    return out


@router.post("/classes", status_code=201)
def create_class(
    body: ClassIn,
    db: Session = Depends(get_db),
    current: Teacher = Depends(get_current_teacher),
):
    _validate_teacher(db, body.homeroom_teacher_id)
    _check_duplicate(db, body.name.strip(), body.academic_year.strip())
    c = Class(
        name=body.name.strip(),
        grade_level=body.grade_level,
        academic_year=body.academic_year.strip(),
        homeroom_teacher_id=body.homeroom_teacher_id,
    )
    db.add(c)
    db.commit()
    teacher = db.get(Teacher, c.homeroom_teacher_id) if c.homeroom_teacher_id else None
    return class_out(c, teacher, [])


@router.get("/classes/{class_id}")
def get_class(class_id: int, db: Session = Depends(get_db)):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    teacher = db.get(Teacher, c.homeroom_teacher_id) if c.homeroom_teacher_id else None

    # per-exam, per-subject class averages; roster attribution uses the
    # enrollment valid at each exam date (same rule as the exam averages page)
    exams = db.query(Exam).order_by(Exam.exam_date, Exam.id).all()
    index_of = {e.id: i for i, e in enumerate(exams)}
    rows = (
        db.query(
            Exam.id,
            ExamSubject.subject,
            ExamSubject.full_score,
            func.avg(ExamResult.score),
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
        .filter(Enrollment.class_id == class_id, ExamResult.status == "entered")
        .group_by(Exam.id, ExamSubject.subject, ExamSubject.full_score)
        .all()
    )
    per_subject: dict[str, dict] = {}
    overall: dict[str, dict] = {}
    for exam_id, subject, full_score, avg in rows:
        rec = per_subject.setdefault(subject, {"full_score": 0.0, "values": [None] * len(exams)})
        rec["full_score"] = max(rec["full_score"], full_score or 0)
        if exam_id in index_of and avg is not None:
            rec["values"][index_of[exam_id]] = round(float(avg), 1)
        o = overall.setdefault(subject, {"full_score": 0.0, "sum": 0.0, "count": 0})
        o["full_score"] = max(o["full_score"], full_score or 0)
        if avg is not None:
            o["sum"] += float(avg)
            o["count"] += 1

    return {
        "class": {
            "id": c.id,
            "name": c.name,
            "grade_level": c.grade_level,
            "academic_year": c.academic_year,
            "homeroom_teacher_id": c.homeroom_teacher_id,
            "homeroom_teacher": teacher.name if teacher else None,
        },
        "students": [
            {"id": s.id, "name": s.name, "gender": s.gender, "admission_no": s.admission_no}
            for s in current_students(db, class_id)
        ],
        "trend": {
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
        },
        "averages": [
            {
                "subject": subject,
                "avg": round(rec["sum"] / rec["count"], 1) if rec["count"] else None,
                "count": rec["count"],
                "full_score": rec["full_score"],
            }
            for subject, rec in sorted(overall.items())
        ],
    }


@router.patch("/classes/{class_id}")
def update_class(
    class_id: int,
    body: ClassIn,
    db: Session = Depends(get_db),
    current: Teacher = Depends(get_current_teacher),
):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    _validate_teacher(db, body.homeroom_teacher_id)
    _check_duplicate(db, body.name.strip(), body.academic_year.strip(), exclude_id=class_id)
    c.name = body.name.strip()
    c.grade_level = body.grade_level
    c.academic_year = body.academic_year.strip()
    c.homeroom_teacher_id = body.homeroom_teacher_id
    db.commit()
    teacher = db.get(Teacher, c.homeroom_teacher_id) if c.homeroom_teacher_id else None
    return class_out(c, teacher, current_students(db, class_id))


@router.delete("/classes/{class_id}")
def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current: Teacher = Depends(get_current_teacher),
):
    c = db.get(Class, class_id)
    if c is None:
        raise HTTPException(status_code=404, detail="class not found")
    if db.query(Enrollment).filter(Enrollment.class_id == class_id).first() is not None:
        raise HTTPException(status_code=409, detail="班级内仍有学生或历史记录，无法删除")
    db.delete(c)
    db.commit()
    return {"ok": True}
