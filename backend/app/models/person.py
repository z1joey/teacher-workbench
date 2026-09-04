"""Person: the single identity table.

Role ("student" | "teacher" | "admin") and role-specific attributes live in
the payload JSONB — e.g. {"role": "student", "name": ..., "admission_no":
...} — only login credentials are typed columns. Adding a role is a new
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
    phone: Mapped[str] = mapped_column(String(40), unique=True)  # login credential — required
    password_hash: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), unique=True)  # optional
    payload: Mapped[dict | None] = mapped_column(JSONType)  # role + role-specific attributes

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    tags = relationship("Tag", secondary="person_tags", back_populates="people")
    events = relationship("Event", secondary="person_events", back_populates="attendees")
    enrollments = relationship("Enrollment", back_populates="person")
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
        # admission_no uniqueness survives life inside JSONB (PG + SQLite >= 3.38).
        Index(
            "uq_person_admission_no",
            text("(payload->>'admission_no')"),
            unique=True,
            sqlite_where=text("payload->>'role' = 'student'"),
            postgresql_where=text("payload->>'role' = 'student'"),
        ),
        # Free-form payload search/filter on PostgreSQL.
        Index("ix_person_payload", "payload", postgresql_using="gin"),
    )


class AuthSession(Base):
    """Bearer tokens for phone/password login (MVP: DB-backed sessions).

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
