"""Drop legacy global uniqueness left over from pre-workspace migrations.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-15

0005/0006 added workspace-scoped indexes but SQLite volumes could still carry:
- table constraint uq_class_name_year on class
- index uq_person_admission_no on person

Either blocks a second teacher from loading demo data.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _table_sql(bind) -> str | None:
    return bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'class'")
    ).scalar()


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
    if not sa.inspect(bind).has_table("class"):
        return False
    return name in {
        idx["name"] for idx in sa.inspect(bind).get_indexes("class")
    }


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("class"):
        return

    if bind.dialect.name == "sqlite":
        ddl = _table_sql(bind) or ""
        if "uq_class_name_year" in ddl:
            with op.batch_alter_table("class") as batch_op:
                batch_op.drop_constraint("uq_class_name_year", type_="unique")
    else:
        insp = sa.inspect(bind)
        constraints = {c["name"] for c in insp.get_unique_constraints("class")}
        if "uq_class_name_year" in constraints:
            op.drop_constraint("uq_class_name_year", "class", type_="unique")

    if not _index_exists(bind, "uq_class_teacher_name_year"):
        op.create_index(
            "uq_class_teacher_name_year",
            "class",
            ["teacher_id", "name", "academic_year"],
            unique=True,
        )

    if sa.inspect(bind).has_table("person") and _index_exists(
        bind, "uq_person_admission_no"
    ):
        if bind.dialect.name == "sqlite":
            op.execute(sa.text("DROP INDEX uq_person_admission_no"))
        else:
            op.drop_index("uq_person_admission_no", table_name="person")

    _STUDENT_WHERE = "payload->>'role' = 'student'"
    if sa.inspect(bind).has_table("person") and not _index_exists(
        bind, "uq_person_workspace_admission_no"
    ):
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
    if not sa.inspect(bind).has_table("class"):
        return

    if _index_exists(bind, "uq_class_teacher_name_year"):
        op.drop_index("uq_class_teacher_name_year", table_name="class")

    if bind.dialect.name == "sqlite":
        ddl = _table_sql(bind) or ""
        if "uq_class_name_year" not in ddl:
            with op.batch_alter_table("class") as batch_op:
                batch_op.create_unique_constraint(
                    "uq_class_name_year", ["name", "academic_year"]
                )
    else:
        insp = sa.inspect(bind)
        constraints = {c["name"] for c in insp.get_unique_constraints("class")}
        if "uq_class_name_year" not in constraints:
            op.create_unique_constraint(
                "uq_class_name_year", "class", ["name", "academic_year"]
            )
