"""Zhipu GLM chat-completions client (OpenAI-compatible endpoint).

The key/model/base URL come from GLM_* env vars or the repo-root .env (see
app.settings). Every failure surfaces as an HTTPException with teacher-facing
Chinese text; callers never see raw provider errors.
"""
import time

import httpx
from fastapi import HTTPException

from .settings import GLM_API_KEY, GLM_BASE_URL, GLM_MODEL

TIMEOUT_SECONDS = 60
# glm-4.7-flash 免费额度常见 429（“访问量过大”）：指数退避重试四次
RETRY_DELAYS = (2, 4, 8, 10)
BUSY_DETAIL = "AI 模型正忙，请稍等片刻再点一次「生成总结」"


def chat(system: str, user: str, *, max_tokens: int = 4096) -> str:
    if not GLM_API_KEY:
        raise HTTPException(
            status_code=503, detail="未配置 GLM_API_KEY，暂不能生成 AI 总结"
        )
    body = {
        "model": GLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "enabled"},
        "temperature": 1.0,
        "max_tokens": max_tokens,
    }
    headers = {"Authorization": f"Bearer {GLM_API_KEY}"}
    resp = None
    for attempt in range(1 + len(RETRY_DELAYS)):
        try:
            resp = httpx.post(
                f"{GLM_BASE_URL}/chat/completions",
                json=body,
                headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except httpx.HTTPError:
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
                continue
            raise HTTPException(status_code=502, detail="AI 服务连接失败，请稍后再试")
        if resp.status_code == 429 and attempt < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[attempt])
            continue
        break
    if resp is None or resp.status_code != 200:
        if resp is not None and resp.status_code == 429:
            raise HTTPException(status_code=502, detail=BUSY_DETAIL)
        raise HTTPException(status_code=502, detail="AI 服务暂时不可用，请稍后再试")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise HTTPException(status_code=502, detail="AI 返回内容异常，请稍后再试")
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=502, detail="AI 未返回内容，请稍后再试")
    return text
