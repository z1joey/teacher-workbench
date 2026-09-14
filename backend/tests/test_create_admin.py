"""create_admin：幂等的管理员引导。

- 已有 admin → 跳过，不改动现有账号
- ADMIN_EMAIL 未注册 → 创建新管理员（密码已哈希）
- ADMIN_EMAIL 已注册为非学生账号 → 原地升级为 admin，密码保持不变
- CLI 缺 ADMIN_EMAIL/ADMIN_PASSWORD 时明确报错退出
"""
from sqlalchemy.orm import sessionmaker

import pytest

from app import create_admin
from app.models import Person
from app.security import verify_password
from tests.conftest import seed_person


def _admins(db):
    return db.query(Person).filter(Person.payload["role"].as_string() == "admin").all()


def _factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def test_ensure_admin_creates_then_skips(db):
    created, action = create_admin.ensure_admin(db, "boss@test.example", "secret123", "管理员")
    assert action == "created"
    assert created.email == "boss@test.example"
    assert created.name == "管理员"
    assert verify_password("secret123", created.password_hash)
    assert len(_admins(db)) == 1

    # 已有 admin：跳过，不新建、不改动
    person, action = create_admin.ensure_admin(db, "other@test.example", "whatever", "别人")
    assert action == "skipped" and person is None
    admins = _admins(db)
    assert len(admins) == 1
    assert admins[0].email == "boss@test.example"


def test_ensure_admin_promotes_existing_teacher(db):
    """ADMIN_EMAIL 已注册为教师时原地升级：角色变 admin，密码不动。"""
    person = seed_person(db, "boss@test.example", name="张三")
    db.commit()

    promoted, action = create_admin.ensure_admin(db, "boss@test.example", "brand-new")
    assert action == "promoted"
    assert promoted.id == person.id
    assert promoted.payload["role"] == "admin"
    # 升级不改密码：ADMIN_PASSWORD 与原密码不同时，原密码仍有效
    assert verify_password("123456", promoted.password_hash)
    assert not verify_password("brand-new", promoted.password_hash)
    assert len(_admins(db)) == 1

    # 升级后再跑：跳过
    _, action = create_admin.ensure_admin(db, "boss@test.example", "brand-new")
    assert action == "skipped"


def test_ensure_admin_refuses_student(db):
    seed_person(db, "kid@test.example", role="student", name="小明", admission_no="2024001")
    db.commit()
    with pytest.raises(SystemExit, match="学生账号"):
        create_admin.ensure_admin(db, "kid@test.example", "secret123")


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
