import uuid
from .associations import Base, student_tag, student_event
from sqlalchemy import Column, DateTime, ForeignKey
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID,  JSONB
from sqlalchemy.orm import mapped_column, Mapped, relationship

class Student(Base):
    """Student-only profile of a Person. Tags live here, not on Person."""
    __tablename__ = "students"
    person_id = Column(UUID, ForeignKey("people.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)

    person = relationship("Person", back_populates="student")
    tags = relationship("Tag", secondary=student_tag, back_populates="students")
    events = relationship("Event", secondary=student_event, back_populates="students")

    payload: Mapped[dict] = mapped_column(JSONB, nullable=True)