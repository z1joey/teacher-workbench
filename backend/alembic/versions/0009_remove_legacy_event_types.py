"""Remove parent_call, activity, talk, tutoring, note_added event types.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-09
"""
from alembic import op

from app.models.event import EVENT_TYPES

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_REMOVED = ("parent_call", "activity", "talk", "tutoring", "note_added")


def _check_sql() -> str:
    return "type IN (%s)" % ", ".join("'%s'" % t for t in EVENT_TYPES)


def upgrade() -> None:
    for event_type in _REMOVED:
        op.execute(f"DELETE FROM event WHERE type = '{event_type}'")
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint("ck_event_type_valid", "event", _check_sql())


def downgrade() -> None:
    op.execute("ALTER TABLE event DROP CONSTRAINT IF EXISTS ck_event_type_valid")
    op.create_check_constraint(
        "ck_event_type_valid", "event",
        "type IN ('birthday', 'exam', 'score', 'parent_meeting', 'activity', "
        "'comment', 'enrolled', 'class_moved', 'exam_taken', 'result_changed', "
        "'seat_changed', 'home_visited', 'talk', 'tutoring', 'parent_call', "
        "'note_added')",
    )
