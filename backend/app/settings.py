"""Runtime settings: plain env vars plus a tiny .env loader for local dev.

The repo-root .env is docker-compose's file; for local dev we also parse its
simple KEY=VALUE lines once at import. Existing environment variables always
win (never overridden), and secrets only ever come from env/.env — never from
source.
"""
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(_REPO_ROOT / ".env")

GLM_API_KEY: str = os.environ.get("GLM_API_KEY", "")
GLM_MODEL: str = os.environ.get("GLM_MODEL", "glm-4.7-flash")
GLM_BASE_URL: str = os.environ.get(
    "GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
)
