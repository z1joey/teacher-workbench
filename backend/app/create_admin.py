"""Ensure an admin account exists, configured via ADMIN_EMAIL / ADMIN_PASSWORD.

幂等引导，三种结果：
- 已有 admin 角色用户 → 跳过（绝不改动现有账号）
- ADMIN_EMAIL 未注册   → 创建新管理员
- ADMIN_EMAIL 已注册为非学生账号 → 原地升级为 admin（密码不变）

未配置环境变量时报错退出，避免静默什么都不做。

用法：python -m app.create_admin   （Docker 内：docker compose exec backend python -m app.create_admin）
"""
import os

from .database import SessionLocal
from .models import Person
from .payloads import validate_person_payload
from .security import hash_password, verify_password

DEFAULT_NAME = "开发者"


def ensure_admin(db, email: str, password: str, name: str = DEFAULT_NAME):
    """返回 (person, action)，action ∈ {"skipped", "created", "promoted"}。

    promoted：邮箱已注册（教师等非学生账号）时原地升级，密码保持不变。
    """
    if (
        db.query(Person)
        .filter(Person.payload["role"].as_string() == "admin")
        .first()
        is not None
    ):
        return None, "skipped"

    existing = db.query(Person).filter(Person.email == email).first()
    if existing is not None:
        if (existing.payload or {}).get("role") == "student":
            raise SystemExit(
                f"{email} 是学生账号，不能升级为 admin（学生档案在 /students 管理）"
            )
        existing.payload = validate_person_payload(
            "admin", {"is_active": (existing.payload or {}).get("is_active", True)}
        )
        db.commit()
        return existing, "promoted"

    admin = Person(
        name=name,
        email=email,
        password_hash=hash_password(password),
        payload=validate_person_payload("admin", {}),
    )
    db.add(admin)
    db.commit()
    return admin, "created"


def main() -> None:
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        raise SystemExit("未配置 ADMIN_EMAIL / ADMIN_PASSWORD，跳过创建管理员")
    if "@" not in email:
        raise SystemExit("ADMIN_EMAIL 需要是合法邮箱地址")
    with SessionLocal() as db:
        person, action = ensure_admin(db, email, password)
    if action == "skipped":
        print("admin 已存在，跳过（不改动现有账号）")
    elif action == "promoted":
        print(f"已将现有账号升级为 admin：{email}（密码不变，用原账号密码登录）")
        if person is not None and not verify_password(password, person.password_hash):
            print("提示：该账号当前密码不是 ADMIN_PASSWORD，请用原密码登录后到个人中心修改")
    else:
        print(f"admin 创建成功：{email}")


if __name__ == "__main__":
    main()
