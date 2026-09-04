"""Many-to-many association tables.

person_events links an event to its attendees: a student-scoped event
(birthday, home visit, score) carries exactly one row, a class-scoped event
(exam, parent meeting) carries many. Only students get tags, by convention
(the payload role isn't FK-checkable).
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Table

from ._common import Base

person_tags = Table(
    "person_tags",
    Base.metadata,
    Column("person_id", ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_person_tags_tag", "tag_id"),
)

person_events = Table(
    "person_events",
    Base.metadata,
    Column("person_id", ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
    Column("event_id", ForeignKey("event.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_person_events_event", "event_id"),
)
