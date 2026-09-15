"""Drop the obsolete gender value "O" (其他) from student payloads.

性别枚举收敛为 F/M，空 = 未填写。历史数据里若存在 gender='O' 的学生，
置为空（未填写）。执行前先在 Python 侧核对行数（可观测）。

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-14
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_CLEAR_O = (
    "UPDATE person SET payload = payload - 'gender' "
    "WHERE payload ->> 'role' = 'student' AND payload ->> 'gender' = 'O'"
)


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.exec_driver_sql(_CLEAR_O)
    print(f"gender 'O' cleanup: {result.rowcount} row(s) updated")


def downgrade() -> None:
    # 枚举收敛为单向收敛（O → 未填写），无可逆操作
    pass
