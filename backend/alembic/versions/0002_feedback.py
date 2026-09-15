"""Feedback table (user feedback from the sidebar entry).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 是「活体 squash」：create_all 用的是当前 metadata，全新数据库在
    # 0001 就已经建出 feedback；只有停在 0001 的老库才需要这里真正建表。
    if sa.inspect(op.get_bind()).has_table("feedback"):
        return
    op.create_table(
        "feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("person.id"), nullable=False),
        sa.Column("feature", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_feedback_person_id"), "feedback", ["person_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_person_id"), table_name="feedback")
    op.drop_table("feedback")
