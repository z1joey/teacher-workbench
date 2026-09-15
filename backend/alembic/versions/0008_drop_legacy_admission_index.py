"""Drop legacy global student admission_no index if still present.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _index_exists(bind, name: str) -> bool:
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
    if not _index_exists(bind, "uq_person_admission_no"):
        return
    if bind.dialect.name == "sqlite":
        op.execute(sa.text("DROP INDEX uq_person_admission_no"))
    else:
        op.drop_index("uq_person_admission_no", table_name="person")


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("person"):
        return
    _STUDENT_WHERE = "payload->>'role' = 'student'"
    if not _index_exists(bind, "uq_person_admission_no"):
        op.create_index(
            "uq_person_admission_no",
            "person",
            [sa.text("(payload->>'admission_no')")],
            unique=True,
            sqlite_where=sa.text(_STUDENT_WHERE),
            postgresql_where=sa.text(_STUDENT_WHERE),
        )
