"""学生 AI 总结：生成（mock GLM，不真实外呼）、保存/列表/编辑/删除。

Summary 是 Event(type="summary")，出席人=[学生, 生成教师]——学生时间线
(GET /students/{id}/timeline) 排除该类型；教师首页最新动态 (dashboard)
按出席人取数，自然出现。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

from app import eventing
from app.models import AuthSession, Event, Person
from app.payloads import validate_person_payload
from app.routers import students as students_router
from app.routers import summaries as summaries_router
from app.security import hash_password
from app.workspace import ensure_workspace_id


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_teacher(db, email="t@t.example") -> Person:
    p = Person(name="王老师", email=email, password_hash=hash_password("123456"),
               payload=validate_person_payload("teacher", {}))
    ensure_workspace_id(p)
    db.add(p)
    db.flush()
    return p


def _seed_student(db, teacher: Person, name: str = "林晓雨",
                  admission_no: str = "S100") -> Person:
    payload = validate_person_payload("student", {"admission_no": admission_no})
    payload["workspace_id"] = ensure_workspace_id(teacher)
    p = Person(name=name, password_hash=hash_password(uuid.uuid4().hex), payload=payload)
    db.add(p)
    db.flush()
    return p


def _headers(db, person: Person, token: str = "t" * 64) -> dict:
    db.add(AuthSession(token=token, person_id=person.id))
    db.commit()
    return {"Authorization": f"Bearer {token}"}


def _seed_comment(db, student: Person, notes: str, start: datetime) -> Event:
    return eventing.create_event(
        db, event_type="comment", title=notes[:100], start_time=start,
        payload={"notes": notes, "about": {"id": str(student.id), "name": student.name}},
        attendee_ids=[student.id], commit=True,
    )


def _seed_other_teacher_client(db, make_client):
    """第二个教师的独立 client（用于越权 404 校验）。"""
    other = _seed_teacher(db, email="other@t.example")
    token = "o" * 64
    db.add(AuthSession(token=token, person_id=other.id))
    db.commit()
    client = make_client(summaries_router.router, students_router.router)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def test_generate_returns_mocked_content(db, make_client):
    teacher = _seed_teacher(db)
    student = _seed_student(db, teacher)
    _seed_comment(db, student, "作业质量提升", datetime(2026, 9, 1, 9, 0))
    headers = _headers(db, teacher)

    client = make_client(summaries_router.router)
    client.app.dependency_overrides[summaries_router.get_glm_chat] = (
        lambda: (lambda system, user: "该生本阶段进步明显。")
    )
    client.headers.update(headers)

    r = client.post(f"/api/students/{student.id}/summary/generate", json={})
    assert r.status_code == 200, r.text
    assert r.json() == {"content": "该生本阶段进步明显。"}

    # 时间段内无记录 → 422，前端据此提示用户
    r = client.post(
        f"/api/students/{student.id}/summary/generate",
        json={"date_from": "2000-01-01", "date_to": "2000-12-31"},
    )
    assert r.status_code == 422
    assert "没有学生记录" in r.json()["detail"]

    # 起止日期倒置 → 422
    r = client.post(
        f"/api/students/{student.id}/summary/generate",
        json={"date_from": "2026-09-10", "date_to": "2026-09-01"},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 保存 / 列表 / 编辑 / 删除
# ---------------------------------------------------------------------------

def _save_summary(client, student_id: str, content: str = "第一阶段总结。") -> dict:
    r = client.post(
        "/api/summaries",
        json={"student_id": student_id, "content": content, "length": "standard",
              "style": "formal", "date_from": "2026-09-01", "date_to": "2026-09-30"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_save_list_patch_delete(db, make_client):
    teacher = _seed_teacher(db)
    student = _seed_student(db, teacher)
    headers = _headers(db, teacher)
    client = make_client(summaries_router.router)
    client.headers.update(headers)

    saved = _save_summary(client, str(student.id))
    assert saved["status"] == "created"

    r = client.get(f"/api/students/{student.id}/summaries")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["content"] == "第一阶段总结。"
    assert items[0]["student_id"] == str(student.id)
    assert items[0]["params"]["length"] == "standard"

    eid = items[0]["id"]
    r = client.patch(f"/api/summaries/{eid}", json={"content": "修改后的总结。"})
    assert r.status_code == 200

    r = client.get(f"/api/students/{student.id}/summaries")
    assert r.json()[0]["content"] == "修改后的总结。"
    assert r.json()[0]["edited"] is True

    r = client.delete(f"/api/summaries/{eid}")
    assert r.status_code == 200
    assert client.get(f"/api/students/{student.id}/summaries").json() == []


def test_other_teacher_cannot_touch_foreign_summary(db, make_client):
    teacher = _seed_teacher(db)
    student = _seed_student(db, teacher)
    owner_client = make_client(summaries_router.router)
    owner_client.headers.update(_headers(db, teacher))
    saved = _save_summary(owner_client, str(student.id))

    stranger = _seed_other_teacher_client(db, make_client)
    eid = saved["id"]
    # 工作区隔离：陌生教师看不到该学生，列表/编辑/删除一律 404
    assert stranger.get(
        f"/api/students/{student.id}/summaries"
    ).status_code == 404
    assert stranger.patch(
        f"/api/summaries/{eid}", json={"content": "越权"}
    ).status_code == 404
    assert stranger.delete(f"/api/summaries/{eid}").status_code == 404


# ---------------------------------------------------------------------------
# 时间线归属：学生时间线排除，教师 dashboard 出现
# ---------------------------------------------------------------------------

def test_student_timeline_excludes_summary(db, make_client):
    teacher = _seed_teacher(db)
    student = _seed_student(db, teacher)
    _seed_comment(db, student, "课堂表现好", datetime(2026, 9, 2, 9, 0))
    headers = _headers(db, teacher)

    client = make_client(summaries_router.router, students_router.router)
    client.headers.update(headers)
    saved = _save_summary(client, str(student.id))

    r = client.get(f"/api/students/{student.id}/timeline")
    assert r.status_code == 200
    types = [e["event_type"] for e in r.json()]
    assert "comment" in types
    assert "summary" not in types


def test_dashboard_includes_summary_for_teacher(db, client, engine):
    """真实应用路由表：教师出席的 summary 出现在首页最新动态。"""
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = Session()
    try:
        teacher = _seed_teacher(db)
        student = _seed_student(db, teacher)
        token = "d" * 64
        db.add(AuthSession(token=token, person_id=teacher.id))
        db.commit()
        eventing.create_event(
            db, event_type="summary", title="学生总结", start_time=datetime(2026, 9, 13, 9, 0),
            payload={"summary": "总结正文", "params": {},
                     "about": {"id": str(student.id), "name": student.name}},
            attendee_ids=[student.id, teacher.id], commit=True,
        )
    finally:
        db.close()

    tc = client
    tc.headers.update({"Authorization": f"Bearer {token}"})
    r = tc.get("/api/dashboard")
    assert r.status_code == 200, r.text
    recent = r.json()["recent_events"]
    summary_rows = [e for e in recent if e["event_type"] == "summary"]
    assert len(summary_rows) == 1
    assert summary_rows[0]["title"] == "学生总结"
    assert summary_rows[0]["students"] == [{"id": str(student.id), "name": student.name}]
