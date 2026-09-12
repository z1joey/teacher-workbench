"""Add class.archived for graduation.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-11
"""
import sqlalchemy as sa
from alembic import op

from app.models.event import EVENT_TYPES

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def _check_sql(types) -> str:
    return "type IN (%s)" % ", ".join("'%s'" % t for t in types)


def upgrade() -> None:
    op.add_column(
        "class",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # EVENT_TYPES now includes graduated; refresh the CHECK to match.
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint("ck_event_type_valid", "event", _check_sql(EVENT_TYPES))


def downgrade() -> None:
    legacy = tuple(t for t in EVENT_TYPES if t != "graduated")
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint("ck_event_type_valid", "event", _check_sql(legacy))
    op.drop_column("class", "archived")
