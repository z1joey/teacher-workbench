from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Semi-structured data (per-question detail, event payloads) lands in JSONB on
# PostgreSQL; the plain JSON variant keeps the SQLite fallback working.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    # Naive UTC: SQLite has no real timezone support; storing aware datetimes
    # would mix string formats and break ordering.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Teacher(Base):
    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(40), unique=True)  # login credential — required
    email: Mapped[str | None] = mapped_column(String(200), unique=True)  # optional
    password_hash: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admission_no: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(10))
    birth_date: Mapped[date | None] = mapped_column(Date)
    guardian_name: Mapped[str | None] = mapped_column(String(100))
    guardian_phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    enrollments: Mapped[list[Enrollment]] = relationship(back_populates="student")


class Class(Base):
    __tablename__ = "class"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    grade_level: Mapped[int] = mapped_column(Integer)
    academic_year: Mapped[str] = mapped_column(String(20))
    homeroom_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"))

    __table_args__ = (UniqueConstraint("name", "academic_year", name="uq_class_name_year"),)

    homeroom_teacher: Mapped[Teacher | None] = relationship()


class Enrollment(Base):
    """Student <-> class membership over time. A class move appends a new row
    and closes the previous one; NULL valid_to means current membership."""

    __tablename__ = "enrollment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("class.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(50))

    student: Mapped[Student] = relationship(back_populates="enrollments")
    class_: Mapped[Class] = relationship()

    __table_args__ = (
        Index(
            "uq_one_current_enrollment",
            "student_id",
            unique=True,
            sqlite_where=text("valid_to IS NULL"),
            postgresql_where=text("valid_to IS NULL"),
        ),
    )


class Exam(Base):
    __tablename__ = "exam"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    exam_date: Mapped[date] = mapped_column(Date)


class ExamSubject(Base):
    __tablename__ = "exam_subject"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exam.id"))
    subject: Mapped[str] = mapped_column(String(50))
    full_score: Mapped[float] = mapped_column(Float)

    __table_args__ = (UniqueConstraint("exam_id", "subject", name="uq_exam_subject"),)

    exam: Mapped[Exam] = relationship()


class KnowledgePoint(Base):
    __tablename__ = "knowledge_point"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_subject_id: Mapped[int] = mapped_column(ForeignKey("exam_subject.id"))
    question_no: Mapped[str] = mapped_column(String(20))
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))
    question_type: Mapped[str | None] = mapped_column(String(30))
    max_score: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("exam_subject_id", "question_no", name="uq_question_no_per_subject"),
    )

    knowledge_point: Mapped[KnowledgePoint | None] = relationship()


class ExamResult(Base):
    __tablename__ = "exam_result"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    exam_subject_id: Mapped[int] = mapped_column(ForeignKey("exam_subject.id"))
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="entered")  # entered | absent
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("student_id", "exam_subject_id", name="uq_result_per_subject"),)


class QuestionResponse(Base):
    __tablename__ = "question_response"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"))
    earned: Mapped[float | None] = mapped_column(Float)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[dict | None] = mapped_column(JSONType)  # chosen option, wrong answer text, ...

    __table_args__ = (
        UniqueConstraint("student_id", "question_id", name="uq_response_per_question"),
        Index("ix_qresp_student", "student_id"),
        Index("ix_qresp_question", "question_id"),
    )


class StudentWeakness(Base):
    __tablename__ = "student_weakness"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_point.id"))
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)  # failed questions so far
    attempts: Mapped[int] = mapped_column(Integer, default=0)  # questions seen in this KP
    severity: Mapped[float] = mapped_column(Float, default=0.0)  # evidence_count / attempts
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | improving | resolved
    first_seen: Mapped[date] = mapped_column(Date)
    last_seen: Mapped[date] = mapped_column(Date)
    last_exam_id: Mapped[int | None] = mapped_column(ForeignKey("exam.id"))

    __table_args__ = (UniqueConstraint("student_id", "knowledge_point_id", name="uq_weakness_per_kp"),)


class HomeVisit(Base):
    __tablename__ = "home_visit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"))
    visited_at: Mapped[datetime] = mapped_column(DateTime)
    purpose: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (Index("ix_visit_student_time", "student_id", "visited_at"),)


class StudentEvent(Base):
    """Append-only timeline. Written in the same transaction as the domain
    change it mirrors; payload JSONB carries display data, ref_* points back."""

    __tablename__ = "student_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    actor_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id"))
    ref_table: Mapped[str | None] = mapped_column(String(50))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)

    __table_args__ = (
        Index("ix_event_student_time", "student_id", "occurred_at"),
        Index("ix_event_type_time", "event_type", "occurred_at"),
    )


class AuthSession(Base):
    """Bearer tokens for phone/password login (MVP: DB-backed sessions)."""

    __tablename__ = "auth_session"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
