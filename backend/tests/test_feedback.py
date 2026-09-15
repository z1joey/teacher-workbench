"""用户反馈：提交 + 管理后台列表。

- 登录用户 POST /feedback（feature 枚举校验、内容必填与长度上限）
- GET /admin/feedback 仅 admin 可见，带作者信息
"""
import uuid

from app.routers import admin, feedback
from tests.conftest import seed_person, seed_token


def _post(client, headers, feature="exams", content="希望考试页能导出 CSV"):
    return client.post(
        "/api/feedback",
        json={"feature": feature, "content": content},
        headers=headers,
    )


def test_submit_feedback_round_trip(make_client, db):
    client = make_client(feedback.router)
    person = seed_person(db, "chen@test.example", name="陈老师")
    headers = {"Authorization": f"Bearer {seed_token(db, person, 'c' * 64)}"}

    r = _post(client, headers)
    assert r.status_code == 201, r.text
    body = r.json()
    uuid.UUID(body["id"])
    assert body["feature"] == "exams"
    assert body["content"] == "希望考试页能导出 CSV"
    assert set(body) == {"id", "feature", "content", "created_at", "resolved_at"}


def test_submit_feedback_validation(make_client, db):
    client = make_client(feedback.router)
    person = seed_person(db, "chen2@test.example")
    headers = {"Authorization": f"Bearer {seed_token(db, person, 'd' * 64)}"}

    assert _post(client, headers, feature="nonexistent").status_code == 422
    assert _post(client, headers, content="   ").status_code == 422
    assert _post(client, headers, content="长" * 2001).status_code == 422

    # 未登录
    assert _post(client, {}).status_code == 401


def test_admin_feedback_list(make_client, db):
    teacher = seed_person(db, "teacher@test.example", name="陈老师")
    fb_client = make_client(feedback.router)
    t_headers = {"Authorization": f"Bearer {seed_token(db, teacher, 'e' * 64)}"}
    assert _post(fb_client, t_headers, feature="home", content="首页很清爽").status_code == 201
    assert _post(fb_client, t_headers, feature="other", content="希望加暗色模式").status_code == 201

    # 教师访问管理列表 → 403
    admin_client = make_client(admin.router, feedback.router)
    assert admin_client.get("/api/admin/feedback", headers=t_headers).status_code == 403

    # admin 可见，最新在前，带作者信息
    boss = seed_person(db, "boss@test.example", role="admin", name="管理员")
    a_headers = {"Authorization": f"Bearer {seed_token(db, boss, 'a' * 64)}"}
    r = admin_client.get("/api/admin/feedback", headers=a_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["content"] for row in rows] == ["希望加暗色模式", "首页很清爽"]
    assert rows[0]["author_name"] == "陈老师"
    assert rows[0]["author_email"] == "teacher@test.example"

    # 未登录 → 401
    assert admin_client.get("/api/admin/feedback").status_code == 401


def test_admin_feedback_resolve_delete_and_count(make_client, db):
    teacher = seed_person(db, "fb-teacher@test.example", name="陈老师")
    fb_client = make_client(feedback.router)
    t_headers = {"Authorization": f"Bearer {seed_token(db, teacher, 'f' * 64)}"}
    r1 = _post(fb_client, t_headers, feature="home", content="第一条")
    r2 = _post(fb_client, t_headers, feature="other", content="第二条")
    assert r1.status_code == r2.status_code == 201

    boss = seed_person(db, "fb-boss@test.example", role="admin", name="管理员")
    admin_client = make_client(admin.router, feedback.router)
    a_headers = {"Authorization": f"Bearer {seed_token(db, boss, 'b' * 64)}"}

    count = admin_client.get("/api/admin/feedback/unresolved-count", headers=a_headers)
    assert count.status_code == 200, count.text
    assert count.json()["count"] == 2

    fid = r1.json()["id"]
    resolved = admin_client.patch(
        f"/api/admin/feedback/{fid}",
        json={"resolved": True},
        headers=a_headers,
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved_at"] is not None

    count2 = admin_client.get("/api/admin/feedback/unresolved-count", headers=a_headers)
    assert count2.json()["count"] == 1

    deleted = admin_client.delete(f"/api/admin/feedback/{r2.json()['id']}", headers=a_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True}

    count3 = admin_client.get("/api/admin/feedback/unresolved-count", headers=a_headers)
    assert count3.json()["count"] == 0

    rows = admin_client.get("/api/admin/feedback", headers=a_headers).json()
    assert len(rows) == 1
    assert rows[0]["id"] == fid
