"""Event: the unified timeline spine — "everything is an event".

A calendar-style row: title, description, start/end, location, attendees —
plus `type`, which says what the payload means (payload is meaningless
without it). Every event is individual; events never reference each other.

Exam scores are per-student score events: one row per student per subject
with {"subject", "score", "max_score"} in the payload. Grouping scores (by
exam sitting or otherwise) is a query-layer concern over payload + time.

Student-scoped events (birthday, home visit, score) list exactly one
attendee; class-scoped events (exam, parent meeting) list the class's
students (or whoever attends).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._common import Base, JSONType, utcnow

EVENT_TYPES = (
    # new vocabulary
    "birthday", "exam", "score", "parent_meeting", "activity",
    # legacy timeline vocabulary — migrated rows + frontend strings keep working
    "enrolled", "class_moved", "exam_taken", "result_changed",
    "home_visited", "talk", "tutoring", "parent_call", "note_added",
)


class Event(Base):
    __tablename__ = "event"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(200))
    payload: Mapped[dict | None] = mapped_column(JSONType)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    attendees = relationship("Person", secondary="person_events", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "type IN (%s)" % ", ".join("'%s'" % t for t in EVENT_TYPES),
            name="ck_event_type_valid",
        ),
        Index("ix_event_type_time", "type", "start_time"),
        Index("ix_event_payload", "payload", postgresql_using="gin"),
    )
