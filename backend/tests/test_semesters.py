from datetime import date

from app.semesters import (
    academic_year_start,
    default_semesters,
    ensure_teacher_semesters,
    semesters_for_academic_year,
)


def test_academic_year_start():
    assert academic_year_start(date(2026, 9, 1)) == 2026
    assert academic_year_start(date(2026, 8, 31)) == 2025


def test_semesters_for_academic_year_follows_9_1_and_2_7_pattern():
    rows = semesters_for_academic_year(2025)
    assert rows == [
        {
            "id": "2025-t1",
            "name": "2025-2026 第一学期",
            "start_date": "2025-09-01",
            "end_date": "2026-01-31",
        },
        {
            "id": "2025-t2",
            "name": "2025-2026 第二学期",
            "start_date": "2026-02-01",
            "end_date": "2026-07-31",
        },
    ]


def test_default_semesters_span_three_years():
    rows = default_semesters(date(2026, 9, 7))
    assert [row["id"] for row in rows] == [
        "2024-t1", "2024-t2",
        "2025-t1", "2025-t2",
        "2026-t1", "2026-t2",
    ]


def test_ensure_teacher_semesters_fills_empty_only():
    filled = ensure_teacher_semesters({"role": "teacher"}, anchor=date(2026, 9, 7))
    assert len(filled["semesters"]) == 6
    custom = [{"id": "x", "name": "自定义", "start_date": "2025-09-01", "end_date": "2026-01-31"}]
    kept = ensure_teacher_semesters({"role": "teacher", "semesters": custom})
    assert kept["semesters"] == custom
