"""Shared building blocks for the app.models package.

All models share the single declarative Base from app.database, so Alembic
autogenerate and metadata.create_all see one coherent schema.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

from ..database import Base

__all__ = ["Base", "JSONType", "utcnow"]

# Semi-structured data (person role payloads, event payloads) lands in JSONB
# on PostgreSQL; the plain JSON variant keeps the SQLite fallback working.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    # Naive UTC: SQLite has no real timezone support; storing aware datetimes
    # would mix string formats and break ordering.
    return datetime.now(timezone.utc).replace(tzinfo=None)
