"""Seed smoke test: run() creates user accounts with the right roles."""
import sys


def test_seed_creates_users_with_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'seed.db'}")
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import seed as seed_mod

    # Idempotency contract: the seed script must be safely re-runnable on an
    # already-seeded DB — the /admin/db/reset flow tells users to re-run it.
    seed_mod.run()
    seed_mod.run()

    from sqlalchemy import inspect

    from app.database import SessionLocal, engine
    from app.models import User

    # run() migrates the schema via Alembic — create_all never creates this table.
    assert "alembic_version" in inspect(engine).get_table_names()

    db = SessionLocal()
    try:
        assert db.query(User).count() == 3
        admin = db.query(User).filter(User.role == "admin").one()
        assert admin.phone == "13800000000"
        chen = db.query(User).filter(User.phone == "13800000001").one()
        assert chen.role == "teacher" and chen.profile.subject == "math"
    finally:
        db.close()
