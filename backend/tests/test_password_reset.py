"""忘记密码：发码（限流/防枚举）+ 校验重置（尝试上限/会话吊销）。

Redis 与 DirectMail 都用内存替身：FakeStore 实现与 PasswordCodeStore 相同
的接口，mailer 记录发送内容。
"""
from __future__ import annotations

import uuid

from fastapi import Depends

from app import password_reset as pr
from app.models import AuthSession, Person
from app.payloads import validate_person_payload
from app.routers import auth as auth_router
from app.security import hash_password, verify_password


# ---------------------------------------------------------------------------
# 替身
# ---------------------------------------------------------------------------

class FakeStore:
    """PasswordCodeStore 的内存替身：存哈希 + 尝试计数，限流逻辑对齐。"""

    def __init__(self):
        self.codes: dict[str, str] = {}
        self.tries: dict[str, int] = {}
        self.cool: dict[str, int] = {}

    def request_code(self, email: str):
        if self.cool.get(email, 0) > 0:
            raise pr.RateLimited(self.cool[email])
        self.cool[email] = 1
        code = "123456"
        self.codes[email] = pr._hash_code(code)
        self.tries[email] = 0
        return code, pr.RESET_CODE_TTL_SECONDS

    def verify_and_consume(self, email: str, code: str):
        stored = self.codes.get(email)
        if stored is None:
            raise pr.CodeError("wrong")
        self.tries[email] += 1
        if self.tries[email] > pr.RESET_MAX_ATTEMPTS:
            self.clear(email)
            raise pr.CodeError("exhausted")
        if stored != pr._hash_code(code.strip()):
            raise pr.CodeError("wrong")
        self.clear(email)

    def clear(self, email: str):
        self.codes.pop(email, None)
        self.tries.pop(email, None)


def _seed_teacher(db, email: str) -> Person:
    payload = validate_person_payload("teacher", {})
    p = Person(name="陈老师", email=email, password_hash=hash_password("123456"),
               payload=payload)
    db.add(p)
    db.commit()
    return p


def _client_with_stubs(make_client, store: FakeStore, sent: list):
    """挂 auth 路由并注入内存 store 与 mailer 替身。"""
    client = make_client(auth_router.router, auth_dependency=False)
    client.app.dependency_overrides[auth_router.get_code_store] = lambda: store
    client.app.dependency_overrides[auth_router.get_mailer] = lambda: (
        lambda to, subject, html: sent.append((to, subject, html))
    )
    return client


# ---------------------------------------------------------------------------
# 发送
# ---------------------------------------------------------------------------

def test_forgot_sends_code_for_known_account(db, make_client):
    store, sent = FakeStore(), []
    client = _client_with_stubs(make_client, store, sent)
    _seed_teacher(db, "chen@school.edu")

    r = client.post("/api/auth/password/forgot", json={"email": "Chen@school.edu "})
    assert r.status_code == 200 and r.json() == {"ok": True}
    # 邮箱规范化后发信、验证码入库（只存哈希）
    assert [to for to, _, _ in sent] == ["chen@school.edu"]
    assert "123456" in sent[0][2]  # HTML 正文包含验证码
    assert list(store.codes.values()) == [pr._hash_code("123456")]


def test_forgot_hides_unknown_accounts(db, make_client):
    store, sent = FakeStore(), []
    client = _client_with_stubs(make_client, store, sent)
    _seed_teacher(db, "chen@school.edu")

    assert client.post(
        "/api/auth/password/forgot", json={"email": "nobody@school.edu"}
    ).json() == {"ok": True}
    assert sent == []  # 未知账号不发信，也不报错


def test_forgot_rate_limits(db, make_client):
    store, sent = FakeStore(), []
    client = _client_with_stubs(make_client, store, sent)
    _seed_teacher(db, "chen@school.edu")
    body = {"email": "chen@school.edu"}

    assert client.post("/api/auth/password/forgot", json=body).status_code == 200
    # 冷却期内 → 429 + Retry-After
    r = client.post("/api/auth/password/forgot", json=body)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert len(sent) == 1


def test_forgot_rejects_bad_email(db, make_client):
    client = _client_with_stubs(make_client, FakeStore(), [])
    r = client.post("/api/auth/password/forgot", json={"email": "x"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 校验 + 重置
# ---------------------------------------------------------------------------

def _request_code(client, email="chen@school.edu"):
    assert client.post("/api/auth/password/forgot", json={"email": email}).status_code == 200
    return "123456"


def test_reset_success_updates_password_and_kills_sessions(db, make_client):
    store, sent = FakeStore(), []
    client = _client_with_stubs(make_client, store, sent)
    teacher = _seed_teacher(db, "chen@school.edu")
    db.add(AuthSession(token="a" * 64, person_id=teacher.id))
    db.add(AuthSession(token="b" * 64, person_id=teacher.id))
    db.commit()
    code = _request_code(client)

    r = client.post("/api/auth/password/reset", json={
        "email": "chen@school.edu", "code": code, "new_password": "newpass1"})
    assert r.status_code == 200 and r.json() == {"ok": True}

    db.expire_all()
    fresh = db.get(Person, teacher.id)
    assert verify_password("newpass1", fresh.password_hash)
    assert not verify_password("123456", fresh.password_hash)
    assert db.query(AuthSession).filter_by(person_id=teacher.id).count() == 0
    assert store.codes.get("chen@school.edu") is None  # 验证码一次性


def test_reset_wrong_code_and_attempt_cap(db, make_client):
    store, sent = FakeStore(), []
    client = _client_with_stubs(make_client, store, sent)
    _seed_teacher(db, "chen@school.edu")
    code = _request_code(client)
    body = {"email": "chen@school.edu", "new_password": "newpass1"}

    for _ in range(pr.RESET_MAX_ATTEMPTS):
        r = client.post("/api/auth/password/reset", json={**body, "code": "000000"})
        assert r.status_code == 400 and "验证码错误" in r.json()["detail"]
    # 第 6 次（即使填对验证码）→ 已作废
    r = client.post("/api/auth/password/reset", json={**body, "code": code})
    assert r.status_code == 400 and "重新获取" in r.json()["detail"]
    # 老密码依然有效
    db.expire_all()
    assert verify_password("123456", db.query(Person).filter_by(
        email="chen@school.edu").one().password_hash)


def test_reset_expired_code_is_rejected(db, make_client):
    client = _client_with_stubs(make_client, FakeStore(), [])
    _seed_teacher(db, "chen@school.edu")
    r = client.post("/api/auth/password/reset", json={
        "email": "chen@school.edu", "code": "123456", "new_password": "newpass1"})
    assert r.status_code == 400 and "验证码错误" in r.json()["detail"]


def test_reset_unknown_email_generic_error(db, make_client):
    client = _client_with_stubs(make_client, FakeStore(), [])
    r = client.post("/api/auth/password/reset", json={
        "email": "nobody@school.edu", "code": "123456", "new_password": "newpass1"})
    # 与"验证码错误"同一文案，不泄露账号是否存在
    assert r.status_code == 400 and r.json()["detail"] == "验证码错误或已过期"


def test_real_password_code_store_roundtrip():
    """真 PasswordCodeStore 的算法层（用 dict 假 redis，不连真 Redis）。"""

    class DictRedis:
        def __init__(self):
            self.kv: dict = {}
            self.ttls: dict = {}

        def set(self, key, value, nx=False, ex=None):
            if nx and key in self.kv:
                return False
            self.kv[key] = value
            if ex:
                self.ttls[key] = ex
            return True

        def get(self, key):
            return self.kv.get(key)

        def incr(self, key):
            self.kv[key] = self.kv.get(key, 0) + 1
            return self.kv[key]

        def expire(self, key, ttl):
            self.ttls[key] = ttl

        def delete(self, *keys):
            for k in keys:
                self.kv.pop(k, None)

        def ttl(self, key):
            return self.ttls.get(key, -1)

    store = pr.PasswordCodeStore(DictRedis())
    code, ttl = store.request_code("a@b.c")
    assert len(code) == 6 and code.isdigit() and ttl == pr.RESET_CODE_TTL_SECONDS
    store.verify_and_consume("a@b.c", code)  # 正确 → 消费成功
    try:
        store.verify_and_consume("a@b.c", code)  # 已消费 → 过期
        raise AssertionError("should raise")
    except pr.CodeError as e:
        assert e.reason == "wrong"
