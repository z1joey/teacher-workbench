"""Scope class name uniqueness to teacher_id (workspace owner).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-15

Drops the legacy ``uq_class_name_year`` object only; the replacement
``uq_class_teacher_name_year`` index is (re)created by 0007. Pre-squash
volumes carry ``uq_class_name_year`` as a UNIQUE constraint, while the
squashed chain would produce an independent index — PostgreSQL rejects
``DROP INDEX`` on a constraint-backing index (DependentObjectsStillExist),
so the constraint form must be checked first.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _table_sql(bind) -> str | None:
    if bind.dialect.name != "sqlite":
        return None
    return bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'class'").scalar()


def _index_exists(bind, name: str) -> bool:
    if bind.dialect.name == "sqlite":
        row = bind.exec_driver_sql("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)).first()
        return row is not None
    if not sa.inspect(bind).has_table("class"):
        return False
    return name in {
        idx["name"] for idx in sa.inspect(bind).get_indexes("class")
    }


def _constraint_exists(bind, name: str) -> bool:
    if bind.dialect.name == "sqlite":
        return name in (_table_sql(bind) or "")
    return name in {
        c["name"] for c in sa.inspect(bind).get_unique_constraints("class")
    }


def _drop_legacy_name_year_unique(bind) -> None:
    if bind.dialect.name == "sqlite":
        if _constraint_exists(bind, "uq_class_name_year"):
            with op.batch_alter_table("class") as batch_op:
                batch_op.drop_constraint("uq_class_name_year", type_="unique")
        elif _index_exists(bind, "uq_class_name_year"):
            op.drop_index("uq_class_name_year", table_name="class")
    elif _constraint_exists(bind, "uq_class_name_year"):
        op.drop_constraint("uq_class_name_year", "class", type_="unique")
    elif _index_exists(bind, "uq_class_name_year"):
        op.drop_index("uq_class_name_year", table_name="class")


def _restore_legacy_name_year_unique(bind) -> None:
    # Historical volumes hold it as a constraint; mirror that on downgrade so
    # re-upgrading stays symmetric (0007.downgrade recreates the same form).
    if _constraint_exists(bind, "uq_class_name_year") or _index_exists(
        bind, "uq_class_name_year"
    ):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("class") as batch_op:
            batch_op.create_unique_constraint(
                "uq_class_name_year", ["name", "academic_year"]
            )
    else:
        op.create_unique_constraint(
            "uq_class_name_year", "class", ["name", "academic_year"]
        )


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("class"):
        return
    _drop_legacy_name_year_unique(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("class"):
        return
    _restore_legacy_name_year_unique(bind)
