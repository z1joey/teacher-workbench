from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..display_name import teacher_display_name
from ..database import get_db
from ..deps import get_current_person
from ..eventing import MANUAL_EVENT_TYPES
from ..models import Class, Enrollment, Event, Person, Tag, person_tags
from ..payloads import validate_person_payload
from ..routers.auth import normalize_phone, validate_phone_format
from ..routers.students import AUTO_HOME_VISIT_TAG_NAME, _prune_unused_tags
from ..unassigned import is_unassigned_class
from ..workspace import classes_query, students_query

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
        "display_name": teacher_display_name(name, email=u.email),
    }
    return out


def settings_out(payload: dict) -> dict:
    return {
        "auto_tags": payload.get("auto_tags", True),
        "calendar_birthdays": payload.get("calendar_birthdays", True),
    }


class ProfileIn(BaseModel):
    # name 为 patch 语义：仅在请求里出现时更新；允许空串 = 清空姓名（显示回退邮箱前缀）
    name: str | None = Field(default=None, max_length=100)
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

    # 毕业归档：已毕业学生与归档班级（数据保留，仅在此集中查看）
    graduated_students = (
        students_query(db, person)
        .filter(Person.payload["graduated_at"].as_string().is_not(None))
        .order_by(Person.payload["graduated_at"].as_string().desc())
        .all()
    )
    archived_classes = []
    for c in (
        classes_query(db, person, include_archived=True)
        .filter(Class.archived.is_(True))
        .order_by(Class.name)
        .all()
    ):
        grads = (
            db.query(Person)
            .join(Enrollment, Enrollment.person_id == Person.id)
            .filter(
                Enrollment.class_id == c.id,
                Person.payload["graduated_at"].as_string().is_not(None),
            )
            .distinct()
            .order_by(Person.payload["admission_no"].as_string())
            .all()
        )
        archived_classes.append(
            {
                "id": str(c.id),
                "name": c.name,
                "academic_year": c.academic_year,
                "students": [
                    {
                        "id": str(s.id),
                        "name": s.name,
                        "admission_no": (s.payload or {}).get("admission_no"),
                    }
                    for s in grads
                ],
            }
        )
    return {
        "user": user_out(person),
        "settings": settings_out(payload),
        "classes": classes,
        "stats": stats,
        "graduated_students": [
            {
                "id": str(s.id),
                "name": s.name,
                "admission_no": (s.payload or {}).get("admission_no"),
                "graduated_at": (s.payload or {}).get("graduated_at"),
            }
            for s in graduated_students
        ],
        "archived_classes": archived_classes,
    }


@router.patch("/profile")
def update_profile(
    body: ProfileIn,
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    payload = dict(person.payload or {})
    if "name" in body.model_fields_set:
        person.name = (body.name or "").strip()

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


@router.post("/profile/clear-home-visit-tags")
def clear_home_visit_tags(
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    """Remove the auto 已家访 tag from every student in this teacher's workspace."""
    tag = db.query(Tag).filter(Tag.name == AUTO_HOME_VISIT_TAG_NAME).first()
    if tag is None:
        return {"removed": 0}
    student_ids = [s.id for s in students_query(db, person).all()]
    if not student_ids:
        return {"removed": 0}
    result = db.execute(
        person_tags.delete().where(
            person_tags.c.person_id.in_(student_ids),
            person_tags.c.tag_id == tag.id,
        )
    )
    removed = int(result.rowcount or 0)
    _prune_unused_tags(db)
    db.commit()
    return {"removed": removed}
