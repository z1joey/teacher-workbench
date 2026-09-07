"""Default school-year semesters for teachers.

Chinese junior/high schools commonly use:
- 第一学期: September → January
- 第二学期: February → July
"""
from __future__ import annotations

from datetime import date

from .payloads import validate_person_payload


def academic_year_start(d: date) -> int:
    """First calendar year of the academic year (2025 for the 2025-2026 year)."""
    return d.year if d.month >= 9 else d.year - 1


def semesters_for_academic_year(start_year: int) -> list[dict]:
    end_year = start_year + 1
    return [
        {
            "id": f"{start_year}-t1",
            "name": f"{start_year}-{end_year} 第一学期",
            "start_date": f"{start_year}-09-01",
            "end_date": f"{end_year}-01-31",
        },
        {
            "id": f"{start_year}-t2",
            "name": f"{start_year}-{end_year} 第二学期",
            "start_date": f"{end_year}-02-01",
            "end_date": f"{end_year}-07-31",
        },
    ]


def default_semesters(anchor: date | None = None, *, span: int = 3) -> list[dict]:
    """Return `span` consecutive academic years of semesters around `anchor`."""
    y = academic_year_start(anchor or date.today())
    first = y - (span - 1)
    rows: list[dict] = []
    for sy in range(first, first + span):
        rows.extend(semesters_for_academic_year(sy))
    return rows


def ensure_teacher_semesters(payload: dict | None, *, anchor: date | None = None) -> dict:
    """Fill empty teacher semesters with defaults; return validated payload."""
    data = dict(payload or {})
    if data.get("role", "teacher") != "teacher":
        return data
    if data.get("semesters"):
        return data
    data["semesters"] = default_semesters(anchor)
    return validate_person_payload("teacher", data)
