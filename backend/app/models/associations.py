from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

student_tag = Table(
    "student_tags",
    Base.metadata,
    Column("student_id", ForeignKey("student.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)

student_event = Table(
    "student_events",
    Base.metadata,
    Column("student_id", ForeignKey("student.id"), primary_key=True),
    Column("event_id", ForeignKey("event.id"), primary_key=True),
)
