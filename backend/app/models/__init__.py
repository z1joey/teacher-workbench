"""Event-centric schema (work in progress — replaces the app/models.py
module, which this package shadows; routers still import the old schema
until they migrate).

Design (2026-09 discussion):

- person is the single identity table; role ("student" | "teacher" |
  "admin") and role-specific attributes live in person.payload.
- everything is an Event: a calendar-style row (title, description,
  start/end, location, attendees) plus a type that gives the payload its
  meaning. Events are individual — no event references another. Exam scores
  are per-student score events with subject/score/max_score in the payload.
- Class/Enrollment stay relational as current state ("who is in class X
  now"), with the partial unique index keeping at most one current
  membership per person.
- Tags attach to persons (students only, by convention) via person_tags.
"""
from .associations import person_events, person_tags
from .class_ import Class, Enrollment
from .event import EVENT_TYPES, Event
from .person import AuthSession, Person
from .tag import Tag

__all__ = [
    "AuthSession",
    "Class",
    "Enrollment",
    "Event",
    "EVENT_TYPES",
    "Person",
    "Tag",
    "person_events",
    "person_tags",
]
