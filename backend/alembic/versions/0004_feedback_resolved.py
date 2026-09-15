"""Feedback resolved_at for admin triage.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("feedback"):
        return
    cols = {c["name"] for c in sa.inspect(bind).get_columns("feedback")}
    if "resolved_at" in cols:
        return
    op.add_column("feedback", sa.Column("resolved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("feedback", "resolved_at")
