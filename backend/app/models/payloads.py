"""Payload schemas: the validation layer for JSONB payloads.

The DB can't check role- or type-specific fields inside JSONB — every write
path funnels through this registry before touching the models. `name` and the
login credentials are typed columns on `person` now (see person.py); only
role-specific attributes stay here.
"""
from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudentPayload(_Strict):
    role: str = "student"
    admission_no: str = Field(max_length=40)
    gender: str | None = None
    birth_date: str | None = None  # ISO "YYYY-MM-DD"
    address: str | None = None
    is_active: bool = True


class TeacherPayload(_Strict):
    role: str = "teacher"
    is_active: bool = True


class AdminPayload(_Strict):
    role: str = "admin"
    is_active: bool = True


class GuardianPayload(_Strict):
    role: str = "guardian"
    # a guardian is a Person too: `name` lives on person.name, the student↔
    # guardian link is student_guardians, contact details ride here
    phone: str | None = None
    relationship: str | None = None  # e.g. 父亲 / 母亲
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


class HomeVisitPayload(_Strict):
    summary: str | None = None
    follow_up: str | None = None
    # guardian of record at visit time (snapshots the student payload;
    # guardians are student attributes, not accounts)
    guardian: str | None = None


class ExamPayload(_Strict):
    term: str | None = None
    # per-subject full_score config of a sitting (subject name -> full score);
    # the score-entry flow reads it to set each score payload's max_score
    full_scores: dict[str, float] | None = None


class ActivityPayload(_Strict):
    # 普通事件 (competitions, activities, ...) created from the events page —
    # the title carries what happened, notes the optional write-up
    notes: str | None = None


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
    "activity": ActivityPayload,
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
    if data is None:
        return data
    schema = EVENT_PAYLOAD_SCHEMAS.get(event_type)
    if schema is None:
        return dict(data)
    return schema(**data).model_dump(exclude_none=True)
