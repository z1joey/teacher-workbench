"""Scope student admission_no uniqueness to workspace_id.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_STUDENT_WHERE = "payload->>'role' = 'student'"


def _index_exists(bind, name: str) -> bool:
    """SQLite cannot reflect expression indexes; query sqlite_master directly."""
    if bind.dialect.name == "sqlite":
        return (
            bind.execute(
                sa.text(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'index' AND name = :name"
                ),
                {"name": name},
            ).first()
            is not None
        )
    if not sa.inspect(bind).has_table("person"):
        return False
    return name in {
        idx["name"] for idx in sa.inspect(bind).get_indexes("person")
    }


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("person"):
        return
    if _index_exists(bind, "uq_person_admission_no"):
        op.drop_index("uq_person_admission_no", table_name="person")
    if not _index_exists(bind, "uq_person_workspace_admission_no"):
        op.create_index(
            "uq_person_workspace_admission_no",
            "person",
            [
                sa.text("(payload->>'workspace_id')"),
                sa.text("(payload->>'admission_no')"),
            ],
            unique=True,
            sqlite_where=sa.text(_STUDENT_WHERE),
            postgresql_where=sa.text(_STUDENT_WHERE),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("person"):
        return
    if _index_exists(bind, "uq_person_workspace_admission_no"):
        op.drop_index("uq_person_workspace_admission_no", table_name="person")
    if not _index_exists(bind, "uq_person_admission_no"):
        op.create_index(
            "uq_person_admission_no",
            "person",
            [sa.text("(payload->>'admission_no')")],
            unique=True,
            sqlite_where=sa.text(_STUDENT_WHERE),
            postgresql_where=sa.text(_STUDENT_WHERE),
        )
