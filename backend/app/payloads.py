"""Payload validation entry point (retained for import compatibility).

The schemas live in app.models.payloads; this module re-exports them so
existing `from app.payloads import ...` call sites keep working.
"""
from .models.payloads import (  # noqa: F401
    EVENT_PAYLOAD_SCHEMAS,
    PERSON_PAYLOAD_SCHEMAS,
    validate_event_payload,
    validate_person_payload,
)
