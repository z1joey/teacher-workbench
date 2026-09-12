"""Remove unused parent_meeting event type.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-09
"""
from alembic import op

from app.models.event import EVENT_TYPES

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _check_sql() -> str:
    return "type IN (%s)" % ", ".join("'%s'" % t for t in EVENT_TYPES)


def upgrade() -> None:
    op.execute("DELETE FROM event WHERE type = 'parent_meeting'")
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint("ck_event_type_valid", "event", _check_sql())


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint(
        "ck_event_type_valid", "event",
        "type IN ('birthday', 'exam', 'score', 'parent_meeting', 'comment', "
        "'enrolled', 'class_moved', 'exam_taken', 'result_changed', "
        "'seat_changed', 'home_visited')",
    )
