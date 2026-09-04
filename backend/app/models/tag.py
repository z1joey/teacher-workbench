"""Tag: global, reusable student tag."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._common import Base, utcnow


class Tag(Base):
    """Global, reusable tag. By convention only attached to persons whose
    payload role is "student" — the DB can't check that (JSONB), the
    validation layer owns it. Only tags attached to at least one person are
    considered "in use"; unused rows are garbage-collected."""

    __tablename__ = "tag"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    color: Mapped[str] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    people = relationship("Person", secondary="person_tags", back_populates="tags")
