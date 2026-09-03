"""Baseline: legacy schema (teacher + is_admin, home_visit) as created by
Base.metadata.create_all before Alembic was introduced.

Revision ID: 0001
Revises:
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_table(
        "student",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admission_no", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("guardian_name", sa.String(length=100), nullable=True),
        sa.Column("guardian_phone", sa.String(length=40), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admission_no"),
    )
    op.create_table(
        "class",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("grade_level", sa.Integer(), nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("homeroom_teacher_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["homeroom_teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "academic_year", name="uq_class_name_year"),
    )
    op.create_table(
        "enrollment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_one_current_enrollment", "enrollment", ["student_id"], unique=True,
        sqlite_where=sa.text("valid_to IS NULL"),
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_table(
        "exam",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "exam_subject",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=50), nullable=False),
        sa.Column("full_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["exam_id"], ["exam.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exam_id", "subject", name="uq_exam_subject"),
    )
    op.create_table(
        "exam_result",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("exam_subject_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("entered_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["exam_subject_id"], ["exam_subject.id"]),
        sa.ForeignKeyConstraint(["entered_by"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "exam_subject_id", name="uq_result_per_subject"),
    )
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
    op.create_table(
        "student_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("actor_teacher_id", sa.Integer(), nullable=True),
        sa.Column("ref_table", sa.String(length=50), nullable=True),
        sa.Column("ref_id", sa.BigInteger(), nullable=True),
        sa.Column("payload", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["student.id"]),
        sa.ForeignKeyConstraint(["actor_teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_student_time", "student_event", ["student_id", "occurred_at"])
    op.create_index("ix_event_type_time", "student_event", ["event_type", "occurred_at"])
    op.create_table(
        "auth_session",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["teacher_id"], ["teacher.id"]),
        sa.PrimaryKeyConstraint("token"),
    )


def downgrade() -> None:
    op.drop_table("auth_session")
    op.drop_index("ix_event_type_time", table_name="student_event")
    op.drop_index("ix_event_student_time", table_name="student_event")
    op.drop_table("student_event")
    op.drop_index("ix_visit_student_time", table_name="home_visit")
    op.drop_table("home_visit")
    op.drop_table("exam_result")
    op.drop_table("exam_subject")
    op.drop_table("exam")
    op.drop_index("uq_one_current_enrollment", table_name="enrollment")
    op.drop_table("enrollment")
    op.drop_table("class")
    op.drop_table("student")
    op.drop_table("teacher")
