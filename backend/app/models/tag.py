from .associations import Base, student_tag
from sqlalchemy import Column, String, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Tag(Base):
    __tablename__ = "tags"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)
    students = relationship("Student", secondary=student_tag, back_populates="tags")