"""Ensure an admin account exists, configured via ADMIN_EMAIL / ADMIN_PASSWORD.

幂等：已有 admin 角色用户时直接跳过（绝不改动现有账号），所以可以放心
重复执行或挂进部署脚本。未配置环境变量时报错退出，避免静默什么都不做。

用法：python -m app.create_admin   （Docker 内：docker compose exec backend python -m app.create_admin）
"""
import os

from .database import SessionLocal
from .models import Person
from .payloads import validate_person_payload
from .security import hash_password

DEFAULT_NAME = "开发者"


def ensure_admin(db, email: str, password: str, name: str = DEFAULT_NAME):
    """admin 不存在时创建并返回；已存在返回 None（跳过，不改动）。"""
    exists = (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "admin")
        .first()
    )
    if exists is not None:
        return None
    admin = Person(
        name=name,
        email=email,
        password_hash=hash_password(password),
        payload=validate_person_payload("admin", {}),
    )
    db.add(admin)
    db.commit()
    return admin


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        raise SystemExit("未配置 ADMIN_EMAIL / ADMIN_PASSWORD，跳过创建管理员")
    if "@" not in email:
        raise SystemExit("ADMIN_EMAIL 需要是合法邮箱地址")
    with SessionLocal() as db:
        created = ensure_admin(db, email, password)
    if created is None:
        print("admin 已存在，跳过（不改动现有账号）")
    else:
        print(f"admin 创建成功：{email}")


if __name__ == "__main__":
    main()
