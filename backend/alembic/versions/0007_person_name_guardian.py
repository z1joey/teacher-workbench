"""person.name column + student_guardians table.

`name` was a role-lifetime field inside each person/student payload; it is
now a typed column shared by every person role (students, teachers, admins,
guardians). This migration adds the column, backfills it from the legacy
payload->>'name' value, and creates the student↔guardian association table
that replaces the flattened guardian_name/guardian_phone the student payload
used to carry. Guardians are Person rows of role "guardian" that can outlive
the student and serve many students.

SQLite dev databases are not migrated — delete the file and re-seed
(python -m app.seed); the migration target is the docker PostgreSQL database.

downgrade drops the association table and the name column; the backfilled
names are lost (they still live in payload->>'name' until re-migrated).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())

    # 1. name column — server_default so existing rows get "" immediately,
    # nullable initially so the backfill below can target the empty rows.
    # Idempotent: on a chain rebuilt from a legacy volume, 0005's create_all
    # (current model metadata) already made the column; only add it when the
    # person table lacks it (a DB migrated incrementally to 0006).
    if "name" not in {c["name"] for c in insp.get_columns("person")}:
        op.add_column(
            "person",
            sa.Column("name", sa.String(100), nullable=True, server_default=""),
        )
    # backfill from the legacy payload value (JSONB -> text, NULL when absent)
    op.execute("UPDATE person SET name = payload->>'name' WHERE payload->>'name' IS NOT NULL")
    op.execute("UPDATE person SET name = '' WHERE name IS NULL")
    op.alter_column(
        "person", "name", existing_type=sa.String(100), nullable=False,
        server_default="",
    )

    # 2. student ↔ guardian association table (idempotent: create_all on a
    # fresh/legacy-volume chain may already have created it)
    if not insp.has_table("student_guardians"):
        op.create_table(
            "student_guardians",
            sa.Column("student_id", sa.Uuid(),
                      sa.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("guardian_id", sa.Uuid(),
                      sa.ForeignKey("person.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("relationship", sa.String(50), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("student_guardians")
    op.drop_column("person", "name")
