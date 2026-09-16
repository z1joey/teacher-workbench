"""DATABASE_URL resolution: explicit env vs POSTGRES_* with URL-encoding."""
from urllib.parse import unquote_plus

import pytest

from app.database import resolve_database_url


def test_resolve_prefers_explicit_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")
    assert resolve_database_url() == "sqlite:///explicit.db"


def test_resolve_builds_postgres_url_with_encoded_password(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("POSTGRES_USER", "tw_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:w/rd")
    monkeypatch.setenv("POSTGRES_DB", "tw_db")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")

    url = resolve_database_url()
    assert url.startswith("postgresql+psycopg://")
    assert "tw_user:p%40ss%3Aw%2Frd@" in url
    assert unquote_plus(url.rsplit("/", 1)[-1]) == "tw_db"
    assert "@db:5432/" in url


def test_resolve_requires_credentials(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_USER", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        resolve_database_url()
