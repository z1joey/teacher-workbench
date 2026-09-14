"""AI 学生总结：GLM 生成 + 保存为 type="summary" 的事件。

A summary is an Event whose attendees are [student, generating teacher], so it
shows up in the teacher's own event feeds (dashboard 最新动态) but never on the
student timeline — students.py excludes type "summary" there, the same way it
excludes "score".
"""
import uuid
from datetime import date
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_person
from ..eventing import create_event
from ..glm import chat as glm_chat
from ..models import Event, Person
from ..models._common import utcnow
from ..workspace import require_student_in_workspace

router = APIRouter(
    tags=["summaries"],
    dependencies=[Depends(get_current_person)],
)

Length = Literal["brief", "standard", "detailed"]
Style = Literal["formal", "warm", "motivational"]

LENGTH_TEXT = {
    "brief": "约50字",
    "standard": "约100字",
    "detailed": "约150字",
}
STYLE_TEXT = {
    "formal": "客观正式，条理清晰，适合写入教学档案",
    "warm": "亲切温暖，面向家长沟通，语气柔和",
    "motivational": "以肯定和鼓励为主，先概括优势再温和指出不足，并给出具体期待",
}

# system-generated bookkeeping that says nothing about how the student is doing
_PROMPT_EXCLUDED_TYPES = ("score", "summary", "birthday")

_SYSTEM_PROMPT = (
    "你是一位中小学班主任，正在为学生撰写阶段性总结。"
    "只输出总结正文本身：不要标题、不要称呼（如“该生”“亲爱的家长”）、"
    "不要署名、不要任何解释或前后缀。"
)


def get_glm_chat():
    """Dependency indirection so tests can stub the network call."""
    return glm_chat


class GenerateIn(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    length: Length = "standard"
    style: Style = "formal"


class SummaryIn(BaseModel):
    student_id: uuid.UUID
    content: str = Field(min_length=1, max_length=8000)
    length: Length | None = None
    style: Style | None = None
    date_from: date | None = None
    date_to: date | None = None


class SummaryUpdateIn(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


def _exam_name_of_score(event: Event) -> str:
    # title convention "<exam name>·<subject>" → prefix is the sitting name
    title = event.title or ""
    return title.rsplit("·", 1)[0] if "·" in title else title


def _in_range(day: date, date_from: date | None, date_to: date | None) -> bool:
    if date_from is not None and day < date_from:
        return False
    if date_to is not None and day > date_to:
        return False
    return True


def _record_line(event: Event) -> str | None:
    day = event.start_time.strftime("%Y年%m月%d日")
    pl = event.payload or {}
    etype = event.type
    if etype == "comment":
        text = (pl.get("notes") or event.title or "").strip()
        return f"{day} 评语：{text}" if text else None
    if etype == "home_visited":
        parts = [f"{day} 家访"]
        if pl.get("guardian"):
            parts.append(f"与{pl['guardian']}")
        if pl.get("purpose"):
            parts.append(f"目的：{pl['purpose']}")
        if pl.get("summary"):
            parts.append(pl["summary"])
        return "，".join(parts)
    if etype == "exam":
        return f"{day} 考试：{event.title}"
    if etype == "seat_changed":
        if pl.get("from") and pl.get("to"):
            return f"{day} 座位调整：{pl['from']} → {pl['to']}"
        return f"{day} 座位调整：{pl.get('to') or '安排座位'}"
    # enrolled / class_moved / graduated / anything else: title + optional summary
    text = (pl.get("summary") or event.title or "").strip()
    return f"{day} {event.title}" if text else None


def _score_lines(db: Session, student_id: uuid.UUID,
                 date_from: date | None, date_to: date | None) -> list[str]:
    rows = (
        db.query(Event)
        .filter(Event.type == "score", Event.attendees.any(Person.id == student_id))
        .order_by(Event.start_time, Event.created_at)
        .all()
    )
    groups: dict[tuple[str, str], list[str]] = {}
    for e in rows:
        day = e.start_time.date()
        if not _in_range(day, date_from, date_to):
            continue
        pl = e.payload or {}
        subj = pl.get("subject") or ""
        value = f"{subj} 缺考" if pl.get("absent") else f"{subj} {pl.get('score')}/{pl.get('max_score')}"
        key = (day.strftime("%Y年%m月%d日"), _exam_name_of_score(e))
        groups.setdefault(key, []).append(value)
    return [
        f"{day} 考试成绩（{name}）：{'、'.join(vals)}"
        for (day, name), vals in sorted(groups.items())
    ]


def _summary_to_dict(e: Event) -> dict:
    pl = e.payload or {}
    about = pl.get("about") or {}
    return {
        "id": str(e.id),
        "student_id": about.get("id"),
        "student_name": about.get("name"),
        "content": pl.get("summary") or "",
        "params": pl.get("params") or {},
        "edited": bool(pl.get("edited")),
        "occurred_at": e.start_time.isoformat(),
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.post("/students/{student_id}/summary/generate")
def generate_summary(
    student_id: uuid.UUID,
    body: GenerateIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
    glm: Callable[..., str] = Depends(get_glm_chat),
):
    """Build a Chinese digest of the student's records in range and ask GLM
    for a summary. Nothing is persisted — the teacher edits, then saves."""
    if body.date_from and body.date_to and body.date_from > body.date_to:
        raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
    student = require_student_in_workspace(db, user, student_id)
    rows = (
        db.query(Event)
        .filter(
            Event.attendees.any(Person.id == student_id),
            Event.type.notin_(_PROMPT_EXCLUDED_TYPES),
        )
        .order_by(Event.start_time, Event.created_at)
        .all()
    )
    lines = [
        line
        for line in (_record_line(e) for e in rows
                     if _in_range(e.start_time.date(), body.date_from, body.date_to))
        if line
    ]
    lines.extend(_score_lines(db, student_id, body.date_from, body.date_to))
    if not lines:
        raise HTTPException(status_code=422, detail="所选时间段内没有学生记录")

    range_text = "{} 至 {}".format(
        body.date_from.isoformat() if body.date_from else "入学以来",
        body.date_to.isoformat() if body.date_to else "今天",
    )
    prompt = (
        f"请根据以下记录，为学生{student.name}写一段阶段性总结。\n"
        f"时间范围：{range_text}\n"
        f"字数要求：{LENGTH_TEXT[body.length]}\n"
        f"风格：{STYLE_TEXT[body.style]}\n"
        f"\n相关记录（按时间先后）：\n" + "\n".join(lines) + "\n\n请直接输出总结正文。"
    )
    return {"content": glm(_SYSTEM_PROMPT, prompt)}


@router.post("/summaries", status_code=201)
def save_summary(
    body: SummaryIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    student = require_student_in_workspace(db, user, body.student_id)
    params: dict = {}
    for key in ("length", "style"):
        value = getattr(body, key)
        if value is not None:
            params[key] = value
    for key in ("date_from", "date_to"):
        value: date | None = getattr(body, key)
        if value is not None:
            params[key] = value.isoformat()
    event = create_event(
        db,
        event_type="summary",
        title="学生总结",
        start_time=utcnow(),
        payload={
            "summary": body.content.strip(),
            "params": params,
            "about": {"id": str(student.id), "name": student.name},
        },
        attendee_ids=[student.id, user.id],
    )
    db.commit()
    return {"id": str(event.id), "student_id": str(student.id), "status": "created"}


@router.get("/students/{student_id}/summaries")
def list_summaries(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    require_student_in_workspace(db, user, student_id)
    rows = (
        db.query(Event)
        .filter(
            Event.type == "summary",
            Event.attendees.any(Person.id == student_id),
            Event.attendees.any(Person.id == user.id),
        )
        .order_by(Event.start_time.desc(), Event.created_at.desc())
        .all()
    )
    return [_summary_to_dict(e) for e in rows]


def _require_own_summary(
    db: Session, user: Person, event_id: uuid.UUID
) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.type != "summary":
        raise HTTPException(status_code=404, detail="summary not found")
    if user.id not in {p.id for p in event.attendees}:
        raise HTTPException(status_code=404, detail="summary not found")
    return event


@router.patch("/summaries/{event_id}")
def update_summary(
    event_id: uuid.UUID,
    body: SummaryUpdateIn,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    event = _require_own_summary(db, user, event_id)
    payload = dict(event.payload or {})
    payload["summary"] = body.content.strip()
    payload["edited"] = True
    event.payload = payload
    db.commit()
    return {"id": str(event.id), "status": "updated"}


@router.delete("/summaries/{event_id}")
def delete_summary(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    event = _require_own_summary(db, user, event_id)
    db.delete(event)
    db.commit()
    return {"ok": True}
