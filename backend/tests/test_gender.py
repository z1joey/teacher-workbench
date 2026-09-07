import pytest
from pydantic import ValidationError

from app.gender import gender_label, parse_gender
from app.payloads import validate_person_payload


def test_parse_gender_from_chinese():
    assert parse_gender("女") == "F"
    assert parse_gender("男") == "M"
    assert parse_gender("其他") == "O"


def test_parse_gender_from_codes_and_aliases():
    assert parse_gender("F") == "F"
    assert parse_gender("female") == "F"
    assert parse_gender("male") == "M"


def test_parse_gender_blank():
    assert parse_gender(None) is None
    assert parse_gender("") is None


def test_parse_gender_unknown():
    with pytest.raises(ValueError, match="无法识别的性别"):
        parse_gender("未知")


def test_gender_label_maps_codes_to_chinese():
    assert gender_label("F") == "女"
    assert gender_label("M") == "男"
    assert gender_label("O") == "其他"
    assert gender_label(None) == ""


def test_student_payload_normalizes_gender_on_validate():
    out = validate_person_payload("student", {
        "admission_no": "S001",
        "gender": "女",
    })
    assert out["gender"] == "F"


def test_student_payload_rejects_unknown_gender():
    with pytest.raises(ValidationError):
        validate_person_payload("student", {
            "admission_no": "S001",
            "gender": "未知",
        })
