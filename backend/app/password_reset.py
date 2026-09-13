"""忘记密码验证码：Redis 存哈希 + 发送/尝试限流。

Codes are 6-digit secrets stored as sha256 hashes with a 10-minute TTL.
Send-side limits (1/min cooldown, 5/hour) and verify-side attempt counting
(5 wrong tries voids the code) live here so the router stays thin. The redis
client is injectable — tests use an in-memory stub.
"""
import hashlib
import secrets
import string
from pathlib import Path

import redis as redis_lib

from .settings import (
    REDIS_URL,
    RESET_CODE_COOLDOWN_SECONDS,
    RESET_CODE_TTL_SECONDS,
    RESET_HOURLY_LIMIT,
    RESET_MAX_ATTEMPTS,
)

_CODE_LENGTH = 6
_CODE_ALPHABET = string.digits  # 纯数字验证码，邮件里大字展示
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "reset_code_email.html"


class RateLimited(Exception):
    """发送过于频繁；retry_after 为需等待的秒数。"""

    def __init__(self, retry_after: int):
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = max(int(retry_after), 1)


class CodeError(Exception):
    """wrong = 验证码错误或过期；exhausted = 尝试次数过多已作废。"""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class PasswordCodeStore:
    """Redis-backed verification-code storage. `client` is a redis-py client
    (decode_responses=True); tests pass an in-memory fake with the same API."""

    def __init__(self, client):
        self.r = client

    def request_code(self, email: str) -> tuple[str, int]:
        """Generate + store a fresh code. Returns (code, ttl_seconds).
        Raises RateLimited when the cooldown or hourly cap trips."""
        cool_key = f"pwd:cool:{email}"
        if not self.r.set(cool_key, 1, nx=True, ex=RESET_CODE_COOLDOWN_SECONDS):
            raise RateLimited(self.r.ttl(cool_key))
        hour_key = f"pwd:hour:{email}"
        sent_this_hour = self.r.incr(hour_key)
        if sent_this_hour == 1:
            self.r.expire(hour_key, 3600)
        if sent_this_hour > RESET_HOURLY_LIMIT:
            raise RateLimited(self.r.ttl(hour_key) or 3600)
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
        self.r.set(f"pwd:code:{email}", _hash_code(code), ex=RESET_CODE_TTL_SECONDS)
        self.r.delete(f"pwd:try:{email}")
        return code, RESET_CODE_TTL_SECONDS

    def verify_and_consume(self, email: str, code: str) -> None:
        """Check the code and clear it on success. Raises CodeError (wrong /
        exhausted) — attempt counting happens before comparison so brute
        force is capped at RESET_MAX_ATTEMPTS."""
        code_key = f"pwd:code:{email}"
        stored = self.r.get(code_key)
        if stored is None:
            raise CodeError("wrong")
        try_key = f"pwd:try:{email}"
        tries = self.r.incr(try_key)
        if tries == 1:
            self.r.expire(try_key, RESET_CODE_TTL_SECONDS)
        if tries > RESET_MAX_ATTEMPTS:
            self.clear(email)
            raise CodeError("exhausted")
        if not secrets.compare_digest(stored, _hash_code(code.strip())):
            raise CodeError("wrong")
        self.clear(email)

    def clear(self, email: str) -> None:
        self.r.delete(f"pwd:code:{email}", f"pwd:try:{email}")


_client: redis_lib.Redis | None = None
_store: PasswordCodeStore | None = None


def get_code_store() -> PasswordCodeStore:
    """FastAPI dependency: process-wide store over one shared connection."""
    global _client, _store
    if _client is None:
        _client = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
    if _store is None:
        _store = PasswordCodeStore(_client)
    return _store


def build_reset_email(code: str) -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return string.Template(template).substitute(
        code=code, minutes=RESET_CODE_TTL_SECONDS // 60
    )
