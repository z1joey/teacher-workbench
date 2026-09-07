from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import MANUAL_EVENT_TYPES
from ..models import Class, Enrollment, Event, Person
from ..payloads import validate_person_payload
from ..semesters import default_semesters, ensure_teacher_semesters

router = APIRouter(tags=["profile"])


def _semesters_out(payload: dict | None) -> list[dict]:
    return list((payload or {}).get("semesters") or [])


def _semesters_for_person(person: Person) -> list[dict]:
    payload = person.payload or {}
    if payload.get("role", "teacher") != "teacher":
        return []
    if payload.get("semesters"):
        return _semesters_out(payload)
    return default_semesters()


def user_out(u: Person) -> dict:
    payload = u.payload or {}
    return {
        "id": str(u.id),
        "name": u.name,
        "phone": u.phone,
        "email": u.email,
        "role": payload.get("role"),
    }


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = None


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    classes = (
        db.query(Class)
        .filter(Class.homeroom_person_id == person.id)
        .order_by(Class.name)
        .all()
    )
    out_classes = []
    for c in classes:
        students = (
            db.query(Person)
            .join(Enrollment, Enrollment.person_id == Person.id)
            .filter(Enrollment.class_id == c.id, Enrollment.valid_to.is_(None))
            .order_by(Person.payload["admission_no"].as_string())
            .all()
        )
        out_classes.append(
            {
                "id": str(c.id),
                "name": c.name,
                "academic_year": c.academic_year,
                "students": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "gender": (s.payload or {}).get("gender"),
                        "admission_no": (s.payload or {}).get("admission_no"),
                    }
                    for s in students
                ],
            }
        )
    attended = Event.attendees.any(Person.id == person.id)
    stats = {
        "interactions": (
            db.query(Event)
            .filter(Event.type.in_(MANUAL_EVENT_TYPES), attended)
            .count()
        ),
        "results_entered": (
            db.query(Event).filter(Event.type == "score", attended).count()
        ),
        "notes_added": (
            db.query(Event).filter(Event.type == "note_added", attended).count()
        ),
    }
    return {
        "user": user_out(person),
        "classes": out_classes,
        "stats": stats,
        "semesters": _semesters_for_person(person),
    }


@router.patch("/profile")
def update_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    payload = dict(person.payload or {})
    person.name = body.name.strip()
    person.email = (body.email or "").strip() or None
    person.payload = payload  # reassign: JSON columns don't see in-place mutation
    db.commit()
    return user_out(person)


class SemesterIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    start_date: str
    end_date: str


class SemestersIn(BaseModel):
    semesters: list[SemesterIn] = Field(default_factory=list)

    @field_validator("semesters")
    @classmethod
    def _unique_ids(cls, rows: list[SemesterIn]) -> list[SemesterIn]:
        ids = [row.id for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("semester ids must be unique")
        return rows


@router.patch("/profile/semesters")
def update_semesters(
    body: SemestersIn,
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    payload = dict(person.payload or {})
    payload["semesters"] = [row.model_dump() for row in body.semesters]
    try:
        person.payload = validate_person_payload(payload.get("role", "teacher"), payload)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return {"semesters": _semesters_out(person.payload)}
