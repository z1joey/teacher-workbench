"""Cross-router regression: new teacher demo seed leaves /profile readable."""
import re
import uuid

from sqlalchemy.dialects.postgresql import dialect as pg_dialect

from app.workspace import archived_class_students_query


def test_demo_seed_profile_readable_for_new_teacher(client, db):
    reg = client.post(
        "/api/auth/register",
        json={"email": "newteacher@test.example", "password": "123456", "name": "新老师"},
    )
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    before = client.get("/api/profile", headers=headers)
    assert before.status_code == 200, before.text
    assert before.json()["stats"]["interactions"] == 0

    seeded = client.post("/api/data/demo/seed", headers=headers)
    assert seeded.status_code == 200, seeded.text

    after = client.get("/api/profile", headers=headers)
    assert after.status_code == 200, after.text
    body = after.json()
    assert len(body["classes"]) >= 2
    assert body["stats"]["interactions"] > 0
    archived = [c for c in body["archived_classes"] if c["name"] == "六1班"]
    assert archived and len(archived[0]["students"]) == 6
    assert len(body["graduated_students"]) == 6


def test_archived_class_students_sql_is_legal_on_postgres(db):
    """SQLite accepts DISTINCT + ORDER BY json extract; PostgreSQL does not.

    Compiling with the PG dialect catches the production GET /profile 500
    (``for SELECT DISTINCT, ORDER BY expressions must appear in select list``)
    without requiring a live Postgres server in the default pytest job.
    """
    sql = str(
        archived_class_students_query(db, uuid.uuid4()).statement.compile(
            dialect=pg_dialect()
        )
    )
    compact = re.sub(r"\s+", " ", sql)
    assert re.search(r"SELECT DISTINCT person\.", compact, re.I) is None
    assert "ORDER BY" in compact.upper()
    assert "->>" in compact
