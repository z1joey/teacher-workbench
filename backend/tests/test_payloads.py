# backend/tests/test_payloads.py
import pytest
from pydantic import ValidationError

from app.payloads import validate_event_payload, validate_person_payload


def test_student_payload_roundtrip():
    out = validate_person_payload("student", {"admission_no": "S1",
                                              "birth_date": "2012-05-14"})
    assert out["role"] == "student" and out["is_active"] is True
    assert "name" not in out  # name lives on the person column, not the payload


def test_student_requires_admission_no():
    with pytest.raises(ValidationError):
        validate_person_payload("student", {})


def test_teacher_payload_carries_no_subject():
    out = validate_person_payload("teacher", {})
    assert out == {"role": "teacher", "is_active": True, "semesters": []}


def test_teacher_semesters_roundtrip():
    rows = [
        {
            "id": "2025-t1",
            "name": "2025-2026 第一学期",
            "start_date": "2025-09-01",
            "end_date": "2026-01-31",
        }
    ]
    out = validate_person_payload("teacher", {"semesters": rows})
    assert out["semesters"] == rows


def test_teacher_semester_end_before_start_rejected():
    with pytest.raises(ValidationError):
        validate_person_payload("teacher", {
            "semesters": [{
                "id": "bad",
                "name": "无效学期",
                "start_date": "2026-03-01",
                "end_date": "2026-02-01",
            }]
        })


def test_guardian_payload_recognized():
    out = validate_person_payload("guardian", {"phone": "13900000001",
                                               "address": "解放路100号"})
    assert out["role"] == "guardian"
    assert out["phone"] == "13900000001"
    assert out["address"] == "解放路100号"
    assert out["is_active"] is True


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        validate_person_payload("coach", {})


def test_score_payload_absent_has_no_score():
    out = validate_event_payload("score", {"subject": "数学", "max_score": 120, "absent": True})
    assert "score" not in out and out["absent"] is True


def test_exam_payload_carries_full_scores():
    out = validate_event_payload("exam", {"full_scores": {"数学": 120}})
    assert out == {"full_scores": {"数学": 120.0}}


def test_exam_payload_carries_subject_colors():
    out = validate_event_payload(
        "exam",
        {"full_scores": {"数学": 120}, "subject_colors": {"数学": "#2E6BA8"}},
    )
    assert out == {
        "full_scores": {"数学": 120.0},
        "subject_colors": {"数学": "#2e6ba8"},
    }


def test_exam_payload_rejects_bad_subject_color():
    with pytest.raises(ValidationError):
        validate_event_payload(
            "exam",
            {"full_scores": {"数学": 120}, "subject_colors": {"数学": "blue"}},
        )


def test_exam_payload_rejects_non_float_full_scores():
    with pytest.raises(ValidationError):
        validate_event_payload("exam", {"full_scores": {"数学": "many"}})


def test_free_form_type_passthrough():
    assert validate_event_payload("birthday", {"foo": 1}) == {"foo": 1}


def test_empty_dict_for_typed_schema_rejected():
    with pytest.raises(ValidationError):
        validate_event_payload("score", {})
