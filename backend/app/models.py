from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    BigInteger,
    CheckConstraint,
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


class User(Base):
    """Login account. `role` picks the permission set; role-specific data
    lives in per-role tables (teacher_profile today, guardian etc. later).
    See docs/superpowers/specs/2026-09-03-user-role-model-design.md."""

    __tablename__ = "user"  # reserved word in PostgreSQL — SQLAlchemy quotes it

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(40), unique=True)  # login credential — required
    email: Mapped[str | None] = mapped_column(String(200), unique=True)  # optional
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # 'admin' | 'teacher'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    profile: Mapped[TeacherProfile | None] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher')", name="ck_user_role_valid"),
    )


class TeacherProfile(Base):
    """Teacher-only attributes, 1:1 with user."""

    __tablename__ = "teacher_profile"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    subject: Mapped[str | None] = mapped_column(String(50))

    user: Mapped[User] = relationship(back_populates="profile")


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
    homeroom_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    __table_args__ = (UniqueConstraint("name", "academic_year", name="uq_class_name_year"),)

    homeroom_teacher: Mapped[User | None] = relationship()


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


class ExamResult(Base):
    __tablename__ = "exam_result"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    exam_subject_id: Mapped[int] = mapped_column(ForeignKey("exam_subject.id"))
    score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="entered")  # entered | absent
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (UniqueConstraint("student_id", "exam_subject_id", name="uq_result_per_subject"),)


class StudentEvent(Base):
    """Append-only timeline. Written in the same transaction as the domain
    change it mirrors; payload JSONB carries display data, ref_* points back."""

    __tablename__ = "student_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    event_type: Mapped[str] = mapped_column(String(40))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    # "once" (default) or "yearly" — birthday events recur every year
    recurrence: Mapped[str] = mapped_column(String(20), default="once", server_default="once")
    actor_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
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
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Tag(Base):
    """Global, reusable student tag. Only tags attached to at least one
    student are considered "in use"; unused rows are garbage-collected."""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    color: Mapped[str] = mapped_column(String(20))


class StudentTag(Base):
    __tablename__ = "student_tag"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"))
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id"))

    __table_args__ = (
        UniqueConstraint("student_id", "tag_id", name="uq_student_tag"),
    )
