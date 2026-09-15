"""用户反馈：登录用户提交对 App 的意见，管理后台查看。

功能模块用 key 存储（前端字典负责展示名），内容上限 2000 字。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..deps import get_current_person
from ..models import Feedback, Person
from ..database import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])

# 与前端下拉框同一份口径（frontend strings.js feedback feature keys）
FEATURES = ("home", "students", "classes", "exams", "visits", "settings", "other")

CONTENT_MAX = 2000


def feedback_out(f: Feedback, author: Person | None = None) -> dict:
    out = {
        "id": str(f.id),
        "feature": f.feature,
        "content": f.content,
        "created_at": f.created_at.isoformat(),
    }
    if author is not None:
        out["author_name"] = author.name
        out["author_email"] = author.email
        out["author_role"] = (author.payload or {}).get("role")
    return out


class FeedbackIn(BaseModel):
    feature: str
    content: str = Field(min_length=1, max_length=CONTENT_MAX)


@router.post("", status_code=201)
def submit_feedback(
    body: FeedbackIn,
    db: Session = Depends(get_db),
    person: Person = Depends(get_current_person),
):
    feature = body.feature.strip()
    if feature not in FEATURES:
        raise HTTPException(status_code=422, detail="功能模块不合法")
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="反馈内容不能为空")
    fb = Feedback(person_id=person.id, feature=feature, content=content)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return feedback_out(fb)


def list_feedback(db: Session, limit: int = 200) -> list[dict]:
    """管理后台列表：最新在前，带作者信息。（供 admin 路由复用）"""
    rows = (
        db.query(Feedback, Person)
        .join(Person, Feedback.person_id == Person.id)
        .order_by(Feedback.created_at.desc())
        .limit(limit)
        .all()
    )
    return [feedback_out(f, author=p) for f, p in rows]
