"""Password hashing and token generation — stdlib only (PBKDF2-HMAC-SHA256)."""
import hashlib
import secrets


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        candidate = hash_password(password, salt)
    except ValueError:
        return False
    return secrets.compare_digest(candidate, stored)


def new_token() -> str:
    return secrets.token_hex(32)
