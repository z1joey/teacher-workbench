"""Payload schemas: the validation layer for JSONB payloads.

The DB can't check role- or type-specific fields inside JSONB — every write
path funnels through this registry before touching the models.
"""
from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudentPayload(_Strict):
    role: str = "student"
    name: str = Field(min_length=1, max_length=100)
    admission_no: str = Field(max_length=40)
    gender: str | None = None
    birth_date: str | None = None  # ISO "YYYY-MM-DD"
    guardian_name: str | None = None
    guardian_phone: str | None = None
    address: str | None = None
    is_active: bool = True


class TeacherPayload(_Strict):
    role: str = "teacher"
    name: str = Field(min_length=1, max_length=100)
    subject: str | None = None
    is_active: bool = True


class AdminPayload(_Strict):
    role: str = "admin"
    name: str = Field(min_length=1, max_length=100)
    is_active: bool = True


PERSON_PAYLOAD_SCHEMAS = {
    "student": StudentPayload,
    "teacher": TeacherPayload,
    "admin": AdminPayload,
}


class ScorePayload(_Strict):
    subject: str = Field(max_length=50)
    max_score: float
    score: float | None = None  # omitted when absent
    absent: bool = False


class NotesPayload(_Strict):
    # talk / tutoring / parent_call / note_added
    notes: str | None = None


class HomeVisitPayload(_Strict):
    summary: str | None = None
    follow_up: str | None = None


class ExamPayload(_Strict):
    term: str | None = None


class EnrolledPayload(_Strict):
    class_name: str | None = None


class ClassMovedPayload(_Strict):
    from_class: str | None = None
    to_class: str | None = None
    reason: str | None = None


EVENT_PAYLOAD_SCHEMAS = {
    "score": ScorePayload,
    "home_visited": HomeVisitPayload,
    "talk": NotesPayload,
    "tutoring": NotesPayload,
    "parent_call": NotesPayload,
    "note_added": NotesPayload,
    "exam": ExamPayload,
    "enrolled": EnrolledPayload,
    "class_moved": ClassMovedPayload,
    # birthday / exam_taken / result_changed / parent_meeting: free-form
}


def validate_person_payload(role: str, data: dict) -> dict:
    schema = PERSON_PAYLOAD_SCHEMAS.get(role)
    if schema is None:
        raise ValueError(f"unknown person role: {role!r}")
    return schema(**data).model_dump()


def validate_event_payload(event_type: str, data: dict | None) -> dict | None:
    if not data:
        return data
    schema = EVENT_PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        return dict(data)
    return schema(**data).model_dump(exclude_none=True)
