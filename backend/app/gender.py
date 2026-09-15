"""Student gender codes (F/M) and Chinese label mapping.

性别只有男/女两种取值，空 = 未填写；不提供「其他」。
"""
from __future__ import annotations

from typing import Literal

GenderCode = Literal["F", "M"]

GENDER_CODES: frozenset[str] = frozenset({"F", "M"})

GENDER_TO_LABEL: dict[str, str] = {
    "F": "女",
    "M": "男",
}

# Import paths and free-text forms normalize to F/M.
GENDER_FROM_TEXT: dict[str, str] = {
    "F": "F",
    "M": "M",
    "f": "F",
    "m": "M",
    "女": "F",
    "男": "M",
    "female": "F",
    "male": "M",
}


def parse_gender(raw: str | None) -> str | None:
    """Normalize a gender cell or form value to F/M, or None when blank."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    code = GENDER_FROM_TEXT.get(text)
    if code is None:
        raise ValueError(f"无法识别的性别: {text}")
    return code


def gender_label(code: str | None) -> str:
    """Map stored code to Chinese label for export/display."""
    if not code:
        return ""
    return GENDER_TO_LABEL.get(code, code)
