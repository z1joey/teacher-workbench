"""Scope class name uniqueness to teacher_id (workspace owner).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
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
    if not sa.inspect(bind).has_table("class"):
        return False
    return name in {
        idx["name"] for idx in sa.inspect(bind).get_indexes("class")
    }


def _table_sql(bind) -> str | None:
    if bind.dialect.name != "sqlite":
        return None
    return bind.execute(
        sa.text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'class'")
    ).scalar()


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("class"):
        return
    if bind.dialect.name == "sqlite":
        ddl = _table_sql(bind) or ""
        if "uq_class_name_year" in ddl:
            with op.batch_alter_table("class") as batch_op:
                batch_op.drop_constraint("uq_class_name_year", type_="unique")
    elif _index_exists(bind, "uq_class_name_year"):
        op.drop_index("uq_class_name_year", table_name="class")
    if not _index_exists(bind, "uq_class_teacher_name_year"):
        op.create_index(
            "uq_class_teacher_name_year",
            "class",
            ["teacher_id", "name", "academic_year"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("class"):
        return
    if _index_exists(bind, "uq_class_teacher_name_year"):
        op.drop_index("uq_class_teacher_name_year", table_name="class")
    if not _index_exists(bind, "uq_class_name_year"):
        op.create_index(
            "uq_class_name_year",
            "class",
            ["name", "academic_year"],
            unique=True,
        )
