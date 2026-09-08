"""Event-centric schema — the application's data model. This package replaced
the flat app/models.py module (deleted along with the legacy schema); every
router imports its models from here.

Design (2026-09 discussion):

- person is the single identity table; name and login credentials are typed
  columns, role ("student" | "teacher" | "admin" | "guardian") and
  role-specific attributes live in person.payload.
- everything is an Event: a calendar-style row (title, description,
  start/end, location, attendees) plus a type that gives the payload its
  meaning. Events are individual — no event references another. Exam scores
  are per-student score events with subject/score/max_score in the payload.
- Class/Enrollment stay relational as current state ("who is in class X
  now"), with the partial unique index keeping at most one current
  membership per person.
- Tags attach to persons (students only, by convention) via person_tags.
- Guardians are Persons linked to students via student_guardians.
"""
from .associations import person_events, person_tags, student_guardians
from .class_ import Class, ClassSeating, Enrollment
from .event import EVENT_TYPES, Event
from .person import AuthSession, Person
from .tag import Tag

__all__ = [
    "AuthSession",
    "Class",
    "ClassSeating",
    "Enrollment",
    "Event",
    "EVENT_TYPES",
    "Person",
    "Tag",
    "person_events",
    "person_tags",
    "student_guardians",
]
