# backend/tests/test_payloads.py
import pytest
from pydantic import ValidationError

from app.payloads import validate_event_payload, validate_person_payload


def test_student_payload_roundtrip():
    out = validate_person_payload("student", {"name": "王明", "admission_no": "S1",
                                              "birth_date": "2012-05-14"})
    assert out["role"] == "student" and out["is_active"] is True


def test_student_requires_admission_no():
    with pytest.raises(ValidationError):
        validate_person_payload("student", {"name": "王明"})


def test_teacher_requires_subject_key_allowed():
    out = validate_person_payload("teacher", {"name": "李老师", "subject": "数学"})
    assert out["subject"] == "数学"


def test_unknown_role_rejected():
    with pytest.raises(ValueError):
        validate_person_payload("guardian", {"name": "x"})


def test_score_payload_absent_has_no_score():
    out = validate_event_payload("score", {"subject": "数学", "max_score": 120, "absent": True})
    assert "score" not in out and out["absent"] is True


def test_free_form_type_passthrough():
    assert validate_event_payload("birthday", {"foo": 1}) == {"foo": 1}
