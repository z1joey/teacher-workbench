"""user/role account model: teacher -> "user" + teacher_profile.

Data-preserving: teacher IDs become user IDs (so auth sessions and every
 FK value stay valid), existing auth_session tokens survive, home_visit
 (dead since the student_event migration) and teacher are dropped.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'teacher')", name="ck_user_role_valid"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "teacher_profile",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # Preserve teacher IDs as user IDs — every existing FK value stays valid.
    op.execute(
        'INSERT INTO "user" (id, name, phone, email, password_hash, role, is_active, created_at) '
        "SELECT id, name, phone, email, password_hash, "
        "CASE WHEN is_admin THEN 'admin' ELSE 'teacher' END, "
        "is_active, created_at FROM teacher"
    )
    op.execute(
        "INSERT INTO teacher_profile (user_id, subject) SELECT id, subject FROM teacher"
        " WHERE subject IS NOT NULL"
    )
    if _is_pg():
        # Copied-in IDs must not collide with the fresh autoincrement sequence.
        op.execute(
            "SELECT setval(pg_get_serial_sequence('\"user\"', 'id'),"
            ' COALESCE((SELECT MAX(id) FROM "user"), 1))'
        )

    # auth_session: teacher_id -> user_id, rows (tokens) preserved.
    with op.batch_alter_table("auth_session") as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute("UPDATE auth_session SET user_id = teacher_id")
    with op.batch_alter_table("auth_session") as batch:
        batch.drop_column("teacher_id")
        batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_auth_session_user_id_user", "user", ["user_id"], ["id"]
        )

    # Domain FKs re-point to "user" (column names intentionally unchanged).
    if _is_pg():
        op.drop_constraint("class_homeroom_teacher_id_fkey", "class", type_="foreignkey")
        op.create_foreign_key(
            "fk_class_homeroom_teacher_id_user", "class", "user",
            ["homeroom_teacher_id"], ["id"],
        )
        op.drop_constraint("exam_result_entered_by_fkey", "exam_result", type_="foreignkey")
        op.create_foreign_key(
            "fk_exam_result_entered_by_user", "exam_result", "user",
            ["entered_by"], ["id"],
        )
        op.drop_constraint("student_event_actor_teacher_id_fkey", "student_event", type_="foreignkey")
        op.create_foreign_key(
            "fk_student_event_actor_teacher_id_user", "student_event", "user",
            ["actor_teacher_id"], ["id"],
        )

    op.drop_index("ix_visit_student_time", table_name="home_visit")
    op.drop_table("home_visit")
    op.drop_table("teacher")


def downgrade() -> None:
    # Best-effort reverse: schema and account data restored; home_visit rows
    # are unrecoverable (they were dropped with the table — the table itself
    # is recreated empty so the schema matches revision 0001 again).
    op.create_table(
        "teacher",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
    )
    op.execute(
        "INSERT INTO teacher (id, name, phone, email, password_hash, subject, is_active, is_admin, created_at) "
        'SELECT u.id, u.name, u.phone, u.email, u.password_hash, tp.subject, u.is_active, '
        "CASE WHEN u.role = 'admin' THEN TRUE ELSE FALSE END, u.created_at "
        'FROM "user" u LEFT JOIN teacher_profile tp ON tp.user_id = u.id'
    )
    if _is_pg():
        op.execute(
            "SELECT setval(pg_get_serial_sequence('teacher', 'id'),"
            " COALESCE((SELECT MAX(id) FROM teacher), 1))"
        )

    if _is_pg():
        op.drop_constraint("fk_class_homeroom_teacher_id_user", "class", type_="foreignkey")
        op.create_foreign_key(
            "class_homeroom_teacher_id_fkey", "class", "teacher",
            ["homeroom_teacher_id"], ["id"],
        )
        op.drop_constraint("fk_exam_result_entered_by_user", "exam_result", type_="foreignkey")
        op.create_foreign_key(
            "exam_result_entered_by_fkey", "exam_result", "teacher",
            ["entered_by"], ["id"],
        )
        op.drop_constraint("fk_student_event_actor_teacher_id_user", "student_event", type_="foreignkey")
        op.create_foreign_key(
            "student_event_actor_teacher_id_fkey", "student_event", "teacher",
            ["actor_teacher_id"], ["id"],
        )

    with op.batch_alter_table("auth_session") as batch:
        batch.add_column(sa.Column("teacher_id", sa.Integer(), nullable=True))
    op.execute("UPDATE auth_session SET teacher_id = user_id")
    with op.batch_alter_table("auth_session") as batch:
        batch.drop_constraint("fk_auth_session_user_id_user", type_="foreignkey")
        batch.drop_column("user_id")
        batch.alter_column("teacher_id", existing_type=sa.Integer(), nullable=False)
    if _is_pg():
        op.create_foreign_key(
            "auth_session_teacher_id_fkey", "auth_session", "teacher",
            ["teacher_id"], ["id"],
        )

    op.drop_table("teacher_profile")
    op.drop_table("user")

    # Recreate home_visit empty (same shape as 0001) so the post-downgrade
    # schema matches revision 0001 exactly and 0001.downgrade stays runnable.
    op.create_table(
        "home_visit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("visited_at", sa.DateTime(), nullable=False),
        sa.Column("purpose", sa.String(length=200), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("follow_up_needed", sa.Boolean(), nullable=False),
        sa.Column("follow_up_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_student_time", "home_visit", ["student_id", "visited_at"])
