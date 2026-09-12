"""Class and Enrollment: current state, kept relational.

Events record history; these tables answer "what is true now" one join deep.
Only persons whose payload role is "student" get enrollments — a convention
the validation layer owns.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._common import Base, utcnow


class Class(Base):
    __tablename__ = "class"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50))
    academic_year: Mapped[str] = mapped_column(String(20))
    # 班级毕业（graduated）后置 True：数据保留，默认从列表隐藏
    archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("0")
    )
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("person.id"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    enrollments = relationship("Enrollment", back_populates="class_")

    __table_args__ = (
        UniqueConstraint("name", "academic_year", name="uq_class_name_year"),
    )


class ClassSeating(Base):
    """班级座位表：一个班一份最新布局。seats 是 {座位序号: 学生 id}，
    序号按行优先从 0 开始；行列变了序号含义跟着变，超界座位在保存时校验。"""

    __tablename__ = "class_seating"

    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class.id"), primary_key=True)
    rows: Mapped[int] = mapped_column()
    cols: Mapped[int] = mapped_column()
    seats: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Enrollment(Base):
    """Student <-> class membership over time. A class move appends a new row
    and closes the previous one; NULL valid_to means current membership, and
    the partial unique index guarantees at most one current membership per
    person."""

    __tablename__ = "enrollment"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id"), index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("class.id"), index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(50))

    person = relationship("Person", back_populates="enrollments")
    class_ = relationship("Class", back_populates="enrollments")

    __table_args__ = (
        Index(
            "uq_one_current_enrollment",
            "person_id",
            unique=True,
            sqlite_where=text("valid_to IS NULL"),
            postgresql_where=text("valid_to IS NULL"),
        ),
    )
