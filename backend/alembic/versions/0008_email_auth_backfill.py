"""Backfill email for existing teacher/admin accounts.

Teachers and admins who registered with phone-only auth need a placeholder
email so they can log in after the switch to email-based authentication.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE person
        SET email = phone || '@migrated.local'
        WHERE email IS NULL
          AND phone IS NOT NULL
          AND payload->>'role' IN ('teacher', 'admin')
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE person
        SET email = NULL
        WHERE email LIKE '%@migrated.local'
          AND payload->>'role' IN ('teacher', 'admin')
    """)
