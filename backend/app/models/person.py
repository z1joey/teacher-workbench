"""Person: the single identity table.

Every human is a Person — a student, teacher, admin, or a student's
guardian. `name` and the login credentials (email/password_hash) are typed
columns; `phone` is optional contact info for teachers/admins. Only
role-specific attributes live in the payload JSONB —
e.g. {"role": "student", "admission_no": ...}. Adding a role is a new
payload shape plus a validation-layer entry, no DDL.

Role-specific rules (only students get tags/enrollments/score events, a
student payload must carry admission_no, ...) are conventions the validation
layer owns; the DB can't express them against JSONB.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._common import Base, JSONType, utcnow


class Person(Base):
    __tablename__ = "person"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # display name — shared identity field for every person role.
    # server_default lets the historical 0005 migration insert legacy rows
    # (whose name still lives in the payload at that checkpoint) without the
    # NOT NULL column rejecting them; 0007 extracts payload->>'name' into it.
    name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    # optional contact for teachers/admins; also used for guardian dedup
    phone: Mapped[str | None] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    # login credential for teachers/admins; NULL for students (they don't log in)
    email: Mapped[str | None] = mapped_column(String(200), unique=True)
    payload: Mapped[dict | None] = mapped_column(JSONType)  # role + role-specific attributes

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    tags = relationship("Tag", secondary="person_tags", back_populates="people")
    events = relationship("Event", secondary="person_events", back_populates="attendees")
    enrollments = relationship("Enrollment", back_populates="person")
    # student ↔ guardian: a student has many guardians, a guardian many students
    guardians = relationship(
        "Person",
        secondary="student_guardians",
        primaryjoin="Person.id == student_guardians.c.student_id",
        secondaryjoin="Person.id == student_guardians.c.guardian_id",
        back_populates="students",
    )
    students = relationship(
        "Person",
        secondary="student_guardians",
        primaryjoin="Person.id == student_guardians.c.guardian_id",
        secondaryjoin="Person.id == student_guardians.c.student_id",
        back_populates="guardians",
    )
    sessions = relationship(
        "AuthSession", back_populates="person", cascade="all, delete-orphan"
    )

    @property
    def role(self) -> str | None:
        return (self.payload or {}).get("role")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    __table_args__ = (
        # Every authz check and "all students" list extracts the role.
        Index("ix_person_role", text("(payload->>'role')")),
        # admission_no is unique within a teacher workspace, not globally.
        Index(
            "uq_person_workspace_admission_no",
            text("(payload->>'workspace_id')"),
            text("(payload->>'admission_no')"),
            unique=True,
            sqlite_where=text("payload->>'role' = 'student'"),
            postgresql_where=text("payload->>'role' = 'student'"),
        ),
        # Free-form payload search/filter on PostgreSQL.
        Index("ix_person_payload", "payload", postgresql_using="gin"),
    )


class AuthSession(Base):
    """Bearer tokens for email/password login (MVP: DB-backed sessions).

    One row per active login (device/browser), so a person can be signed in
    from several at once; delete one row to log out that device, all of them
    to log out everywhere (e.g. after a password change).
    """

    __tablename__ = "auth_session"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    person = relationship("Person", back_populates="sessions")
