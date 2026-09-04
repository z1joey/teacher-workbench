from .associations import Base, student_event
from sqlalchemy import Column, String, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class Event(Base):
    __tablename__ = "events"
    event_id = Column(String, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    students = relationship("Student", secondary=student_event, back_populates="events")
    payload = mapped_column(JSONB, nullable=True)