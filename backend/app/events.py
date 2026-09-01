"""Timeline helper: every domain write should also append a student_event row
in the same transaction, so the timeline is complete without reconciliation."""
from datetime import datetime

from sqlalchemy.orm import Session

from .models import StudentEvent


def add_event(
    db: Session,
    student_id: int,
    event_type: str,
    occurred_at: datetime,
    actor_teacher_id: int | None = None,
    ref_table: str | None = None,
    ref_id: int | None = None,
    payload: dict | None = None,
) -> StudentEvent:
    event = StudentEvent(
        student_id=student_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor_teacher_id=actor_teacher_id,
        ref_table=ref_table,
        ref_id=ref_id,
        payload=payload or {},
    )
    db.add(event)
    return event
