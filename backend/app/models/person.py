import uuid
from .associations import Base
from sqlalchemy import Column, String, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

class Person(Base):
    __tablename__ = "people"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now)

    role = relationship("Role", back_populates="person", uselist=False)