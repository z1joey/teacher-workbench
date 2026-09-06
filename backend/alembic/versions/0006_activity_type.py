"""activity event type: relax ck_event_type_valid to admit type="activity".

The events page gains 普通事件 (competitions, activities, ...) as its own
Event type — created from the events page, so existing PostgreSQL databases
need the CHECK constraint rebuilt from the EVENT_TYPES list without it. The
constraint text is regenerated from app.models.EVENT_TYPES, so this migration
stays in lockstep with the model by construction.

downgrade re-imposes the previous vocabulary; activity rows (if any) are
deleted first, since they would violate the restored constraint.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-05
"""
from alembic import op

from app.models.event import EVENT_TYPES

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _check_sql() -> str:
    return "type IN (%s)" % ", ".join("'%s'" % t for t in EVENT_TYPES)


def upgrade() -> None:
    op.drop_constraint("ck_event_type_valid", "event", type_="check")
    op.create_check_constraint("ck_event_type_valid", "event", _check_sql())


def downgrade() -> None:
    op.execute("DELETE FROM event WHERE type = 'activity'")
    op.drop_constraint("ck_event_type_valid", "event", type_="check")
    op.create_check_constraint(
        "ck_event_type_valid", "event",
        "type IN ('birthday', 'exam', 'score', 'parent_meeting', "
        "'enrolled', 'class_moved', 'exam_taken', 'result_changed', "
        "'home_visited', 'talk', 'tutoring', 'parent_call', 'note_added')",
    )
