"""Payload schemas: the validation layer for JSONB payloads.

The DB can't check role- or type-specific fields inside JSONB — every write
path funnels through this registry before touching the models. `name` and the
login credentials are typed columns on `person` now (see person.py); only
role-specific attributes stay here.
"""
import re
from typing import Literal

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..gender import GENDER_CODES, parse_gender


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudentPayload(_Strict):
    role: str = "student"
    admission_no: str = Field(max_length=40)
    gender: Literal["F", "M", "O"] | None = None
    birth_date: str | None = None  # ISO "YYYY-MM-DD"
    address: str | None = None
    workspace_id: str | None = None
    is_active: bool = True

    @field_validator("gender", mode="before")
    @classmethod
    def _normalize_gender(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str) and value in GENDER_CODES:
            return value
        return parse_gender(value if isinstance(value, str) else str(value))


class TeacherPayload(_Strict):
    role: str = "teacher"
    workspace_id: str | None = None
    is_active: bool = True
    auto_tags: bool = True
    name_display: Literal["full", "teacher"] = "full"
    calendar_birthdays: bool = True


class AdminPayload(_Strict):
    role: str = "admin"
    is_active: bool = True


class GuardianPayload(_Strict):
    role: str = "guardian"
    # a guardian is a Person too: `name` lives on person.name, the student↔
    # guardian link is student_guardians (which carries the relationship),
    # contact details ride here
    phone: str | None = None
    address: str | None = None
    is_active: bool = True


PERSON_PAYLOAD_SCHEMAS = {
    "student": StudentPayload,
    "teacher": TeacherPayload,
    "admin": AdminPayload,
    "guardian": GuardianPayload,
}


class ScorePayload(_Strict):
    subject: str = Field(max_length=50)
    max_score: float
    score: float | None = None  # omitted when absent
    absent: bool = False


class NotesPayload(_Strict):
    # talk / tutoring / parent_call / note_added
    notes: str | None = None


class MentionedStudent(_Strict):
    id: str = Field(max_length=40)
    name: str = Field(max_length=100)


class CommentPayload(_Strict):
    notes: str | None = None
    mentioned: list[MentionedStudent] | None = None
    about: MentionedStudent | None = None  # primary student the comment is about


class HomeVisitPayload(_Strict):
    summary: str | None = None
    purpose: str | None = None
    done: bool | None = None
    # guardian of record at visit time (snapshots the student payload;
    # guardians are student attributes, not accounts)
    guardian: str | None = None


_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class ExamPayload(_Strict):
    term: str | None = None
    # per-subject full_score config of a sitting (subject name -> full score);
    # the score-entry flow reads it to set each score payload's max_score
    full_scores: dict[str, float] | None = None
    # optional theme color per subject (hex); charts and pills fall back to
    # the frontend catalog when a subject has none stored
    subject_colors: dict[str, str] | None = None

    @field_validator("subject_colors")
    @classmethod
    def _hex_colors(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if not value:
            return value
        out = {}
        for key, color in value.items():
            if not isinstance(color, str) or not _COLOR_RE.match(color):
                raise ValueError(f"invalid subject color: {color!r}")
            out[key] = color.lower()
        return out


class ActivityPayload(_Strict):
    # 普通事件 (competitions, activities, ...) created from the events page —
    # the title carries what happened, notes the optional write-up
    notes: str | None = None


class EnrolledPayload(_Strict):
    class_name: str | None = None
    notes: str | None = None


class ClassMovedPayload(_Strict):
    from_class: str | None = None
    to_class: str | None = None
    reason: str | None = None
    notes: str | None = None


EVENT_PAYLOAD_SCHEMAS = {
    "score": ScorePayload,
    "home_visited": HomeVisitPayload,
    "talk": NotesPayload,
    "tutoring": NotesPayload,
    "parent_call": NotesPayload,
    "note_added": NotesPayload,
    "comment": CommentPayload,
    "exam": ExamPayload,
    "activity": ActivityPayload,
    "enrolled": EnrolledPayload,
    "class_moved": ClassMovedPayload,
    # birthday / exam_taken / result_changed / parent_meeting: free-form
}


def validate_person_payload(role: str, data: dict) -> dict:
    data = dict(data)
    if role == "teacher":
        data.pop("semesters", None)
    schema = PERSON_PAYLOAD_SCHEMAS.get(role)
    if schema is None:
        raise ValueError(f"unknown person role: {role!r}")
    return schema(**data).model_dump()


def validate_event_payload(event_type: str, data: dict | None) -> dict | None:
    if data is None:
        return data
    schema = EVENT_PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        return dict(data)
    return schema(**data).model_dump(exclude_none=True)
