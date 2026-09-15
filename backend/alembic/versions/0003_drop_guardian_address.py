"""Strip the obsolete address key from guardian payloads.

学生档案已有家庭住址；监护人不再单独存地址。生产库为 PostgreSQL，用
jsonb 操作符一步清理；执行前先在 Python 侧核对行数（可观测）。

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-14
"""
import json

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_SELECT_GUARDIANS = "SELECT id, payload FROM person WHERE payload ->> 'role' = 'guardian'"
_UPDATE_PAYLOAD = "UPDATE person SET payload = %s WHERE id = %s"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.exec_driver_sql(_SELECT_GUARDIANS).fetchall()
    cleaned = 0
    for pid, payload in rows:
        data = dict(payload or {})
        if "address" not in data:
            continue
        data.pop("address")
        conn.exec_driver_sql(_UPDATE_PAYLOAD, (json.dumps(data, ensure_ascii=False), pid))
        cleaned += 1
    print(f"guardian address cleanup: {cleaned} row(s) updated")


def downgrade() -> None:
    # 一次性数据清理，无可逆操作（旧值已弃用）
    pass
