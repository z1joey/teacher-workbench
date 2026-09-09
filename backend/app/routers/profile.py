from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..display_name import teacher_display_name
from ..database import get_db
from ..deps import get_current_person
from ..eventing import MANUAL_EVENT_TYPES
from ..models import Class, Enrollment, Event, Person
from ..payloads import validate_person_payload
from ..routers.auth import normalize_phone, validate_phone_format
from ..unassigned import is_unassigned_class
from ..workspace import classes_query

router = APIRouter(tags=["profile"])


def user_out(u: Person) -> dict:
    payload = u.payload or {}
    role = payload.get("role")
    name = u.name
    out = {
        "id": str(u.id),
        "name": name,
        "phone": u.phone,
        "email": u.email,
        "role": role,
    }
    if role == "teacher":
        out["display_name"] = teacher_display_name(name)
    else:
        out["display_name"] = name or ""
    return out


def settings_out(payload: dict) -> dict:
    return {
        "auto_tags": payload.get("auto_tags", True),
        "calendar_birthdays": payload.get("calendar_birthdays", True),
    }


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    auto_tags: bool | None = None
    calendar_birthdays: bool | None = None


@router.get("/profile")
def get_profile(
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    payload = dict(person.payload or {})
    classes = []
    for c in classes_query(db, person).order_by(Class.name).all():
        if is_unassigned_class(c):
            continue
        students = (
            db.query(Person)
            .join(Enrollment, Enrollment.person_id == Person.id)
            .filter(Enrollment.class_id == c.id, Enrollment.valid_to.is_(None))
            .order_by(Person.payload["admission_no"].as_string())
            .all()
        )
        classes.append(
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
        "comments_written": (
            db.query(Event).filter(Event.type == "comment", attended).count()
        ),
    }
    return {
        "user": user_out(person),
        "settings": settings_out(payload),
        "classes": classes,
        "stats": stats,
    }


@router.patch("/profile")
def update_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    payload = dict(person.payload or {})
    person.name = body.name.strip()

    if "phone" in body.model_fields_set:
        raw = (body.phone or "").strip()
        if not raw:
            person.phone = None
        else:
            phone = normalize_phone(raw)
            validate_phone_format(phone)
            conflict = (
                db.query(Person)
                .filter(Person.phone == phone, Person.id != person.id)
                .first()
            )
            if conflict is not None:
                raise HTTPException(status_code=409, detail="该手机号已注册")
            person.phone = phone

    if "auto_tags" in body.model_fields_set and body.auto_tags is not None:
        payload["auto_tags"] = body.auto_tags
    if "calendar_birthdays" in body.model_fields_set and body.calendar_birthdays is not None:
        payload["calendar_birthdays"] = body.calendar_birthdays
    person.payload = validate_person_payload("teacher", payload)
    db.commit()
    return {**user_out(person), "settings": settings_out(person.payload or {})}
