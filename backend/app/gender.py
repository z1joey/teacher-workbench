"""Student gender codes (F/M/O) and Chinese label mapping."""
from __future__ import annotations

from typing import Literal

GenderCode = Literal["F", "M", "O"]

GENDER_CODES: frozenset[str] = frozenset({"F", "M", "O"})

GENDER_TO_LABEL: dict[str, str] = {
    "F": "女",
    "M": "男",
    "O": "其他",
}

# Import paths and free-text forms normalize to F/M/O.
GENDER_FROM_TEXT: dict[str, str] = {
    "F": "F",
    "M": "M",
    "O": "O",
    "f": "F",
    "m": "M",
    "o": "O",
    "女": "F",
    "男": "M",
    "其他": "O",
    "female": "F",
    "male": "M",
}


def parse_gender(raw: str | None) -> str | None:
    """Normalize a gender cell or form value to F/M/O, or None when blank."""
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
