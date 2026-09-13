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

# ---------------------------------------------------------------- 忘记密码

# Redis 存验证码 + 限流；不可用时验证码功能报 503，不影响其他功能
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")

# 阿里云 DirectMail（发信地址须已在控制台验证通过）
ALI_ACCESS_KEY_ID: str = os.environ.get("ALI_ACCESS_KEY_ID", "")
ALI_ACCESS_KEY_SECRET: str = os.environ.get("ALI_ACCESS_KEY_SECRET", "")
ALI_NO_REPLY_EMAIL: str = os.environ.get("ALI_NO_REPLY_EMAIL", "")
ALI_DM_REGION: str = os.environ.get("ALI_DM_REGION", "cn-hangzhou")

RESET_CODE_TTL_SECONDS = 600        # 验证码有效期 10 分钟
RESET_CODE_COOLDOWN_SECONDS = 60    # 同邮箱发送冷却 1 分钟
RESET_HOURLY_LIMIT = 5              # 同邮箱每小时最多 5 封
RESET_MAX_ATTEMPTS = 5              # 验证码最多尝试 5 次
RESET_FROM_ALIAS = "教师工作台"

