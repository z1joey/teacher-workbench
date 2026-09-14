"""create_admin：幂等的管理员引导。

- 无 admin 时按入参创建（payload role=admin，密码已哈希）
- 已有 admin 时跳过且不动现有账号
- CLI 缺 ADMIN_EMAIL/ADMIN_PASSWORD 时明确报错退出
"""
from sqlalchemy.orm import sessionmaker

import pytest

from app import create_admin
from app.models import Person
from app.security import verify_password


def _admins(db):
    return db.query(Person).filter(Person.payload["role"].as_string() == "admin").all()


def _factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_ensure_admin_creates_then_skips(db):
    created = create_admin.ensure_admin(db, "boss@test.example", "secret123", "管理员")
    assert created is not None
    assert created.email == "boss@test.example"
    assert created.name == "管理员"
    assert verify_password("secret123", created.password_hash)
    assert len(_admins(db)) == 1

    # 第二次：跳过，不新建、不改动
    again = create_admin.ensure_admin(db, "other@test.example", "whatever", "别人")
    assert again is None
    admins = _admins(db)
    assert len(admins) == 1
    assert admins[0].email == "boss@test.example"


def test_main_requires_env(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with pytest.raises(SystemExit, match="ADMIN_EMAIL"):
        create_admin.main()


def test_main_creates_then_skips(monkeypatch, engine):
    monkeypatch.setenv("ADMIN_EMAIL", "boss@test.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")
    factory = _factory(engine)
    monkeypatch.setattr(create_admin, "SessionLocal", factory)

    create_admin.main()
    db = factory()
    try:
        admins = _admins(db)
        assert len(admins) == 1
        assert admins[0].email == "boss@test.example"
        assert verify_password("secret123", admins[0].password_hash)
    finally:
        db.close()

    # 已存在：再跑一次跳过，不新建
    create_admin.main()
    db = factory()
    try:
        assert len(_admins(db)) == 1
    finally:
        db.close()
