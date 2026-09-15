"""Remove legacy guardian address from person payloads.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-15

Home address is stored on the student only; guardians share it implicitly.
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("person"):
        return
    rows = bind.execute(
        sa.text(
            "SELECT id, payload FROM person "
            "WHERE json_extract(payload, '$.role') = 'guardian'"
        )
    ).fetchall()
    for row in rows:
        raw = row[1]
        if not raw:
            continue
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
        if "address" not in payload:
            continue
        payload.pop("address", None)
        bind.execute(
            sa.text("UPDATE person SET payload = :payload WHERE id = :id"),
            {"payload": json.dumps(payload, ensure_ascii=False), "id": row[0]},
        )


def downgrade() -> None:
    pass
