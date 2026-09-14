"""Initial schema (v1 launch).

Squashed replacement for the pre-release 0001–0011 Alembic chain. Builds the
current event-centric schema from SQLAlchemy models.

Revision ID: 0001
Revises:
Create Date: 2026-09-14
"""
from alembic import op

import app.models  # noqa: F401 — register tables on Base.metadata
from app.database import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
