"""Behavior lock for the auth core: register / login → /me → logout over
app.routers.auth, plus the /profile and /teachers reads that ride on the same
identity."""
from __future__ import annotations

import uuid

from app.models import AuthSession, Person
from app.routers import auth, misc, profile
from tests.conftest import seed_person, seed_token


def _register(client, email: str, password: str = "secret123", **extra):
    return client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def _auth_client(make_client):
    # /register and /login must be open; /me and /logout guard themselves.
    return make_client(auth.router, auth_dependency=False)


def test_register_login_me_logout_flow(make_client, db):
    client = _auth_client(make_client)
    r = _register(client, "teacher@test.example", name="李老师")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["role"] == "teacher"
    uuid.UUID(body["user"]["id"])
    assert db.get(AuthSession, body["token"]).person_id == uuid.UUID(body["user"]["id"])

    r = client.post("/api/auth/login", json={"email": "teacher@test.example", "password": "secret123"})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert set(me.json()) == {"id", "name", "phone", "email", "role", "display_name"}
    assert me.json()["id"] == body["user"]["id"]
    assert me.json()["name"] == "李老师"
    assert me.json()["role"] == "teacher"

    assert client.post("/api/auth/logout", headers=headers).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_register_cannot_mint_admin(make_client):
    client = _auth_client(make_client)
    r = _register(client, "teacher2@test.example", password="123456", role="admin")
    assert r.status_code == 201, r.text
    assert r.json()["user"]["role"] == "teacher"


def test_register_without_name_stores_empty_and_displays_email_prefix(make_client):
    """注册未填姓名：入库为空串（=未设置），display_name 回退邮箱前缀。"""
    client = _auth_client(make_client)
    r = _register(client, "localpart@example.com", password="123456")
    assert r.json()["user"]["name"] == ""
    assert r.json()["user"]["display_name"] == "localpart"
    r = _register(client, "other@example.com", password="123456", name="  ")
    assert r.json()["user"]["name"] == ""
    assert r.json()["user"]["display_name"] == "other"


def test_register_duplicate_email_409(make_client):
    client = _auth_client(make_client)
    assert _register(client, "dup@test.example", password="123456").status_code == 201
    r = _register(client, "dup@test.example", password="123456", name="别人")
    assert r.status_code == 409


def test_register_without_phone_succeeds(make_client):
    client = _auth_client(make_client)
    r = _register(client, "nophone@test.example", password="123456", name="王老师")
    assert r.status_code == 201, r.text
    assert r.json()["user"]["phone"] is None
    assert r.json()["user"]["email"] == "nophone@test.example"


def test_login_me_logout_flow(make_client, db):
    client = _auth_client(make_client)
    person = seed_person(db, "teacher@test.example", name="李老师")
    db.commit()

    r = client.post("/api/auth/login", json={"email": "teacher@test.example", "password": "123456"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["name"] == "李老师"
    headers = {"Authorization": f"Bearer {body['token']}"}

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert set(me.json()) == {"id", "name", "phone", "email", "role", "display_name"}
    assert me.json()["id"] == body["user"]["id"]
    assert me.json()["role"] == "teacher"

    assert client.post("/api/auth/logout", headers=headers).json() == {"ok": True}
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_login_wrong_password_401(make_client, db):
    client = _auth_client(make_client)
    seed_person(db, "wrongpass@test.example", name="王老师")
    r = client.post("/api/auth/login", json={"email": "wrongpass@test.example", "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_without_token_401(make_client):
    client = _auth_client(make_client)
    assert client.get("/api/auth/me").status_code == 401


def test_disabled_person_gets_403_on_me(make_client, db):
    client = _auth_client(make_client)
    person = seed_person(db, "disabled@test.example", active=False)
    token = seed_token(db, person, "a" * 64)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_profile_patch_get_round_trips_name(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "profile@test.example", name="陈老师")
    token = seed_token(db, person, "b" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/profile", json={"name": "陈老师"}, headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"id", "name", "phone", "email", "role", "settings", "display_name"}
    assert r.json()["settings"] == {
        "auto_tags": True,
        "calendar_birthdays": True,
    }
    assert r.json()["name"] == "陈老师"

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {
        "user", "classes", "stats", "settings",
        "graduated_students", "archived_classes",
    }
    assert r.json()["settings"] == {
        "auto_tags": True,
        "calendar_birthdays": True,
    }
    assert r.json()["user"]["name"] == "陈老师"


def test_profile_patch_name_is_optional_and_clearable(make_client, db):
    """姓名为 patch 语义：可不带（只改设置）、可传空串清空（显示回退邮箱前缀）。"""
    client = make_client(profile.router)
    person = seed_person(db, "noname@test.example", name="陈老师")
    token = seed_token(db, person, "h" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    # 不带 name 键：姓名保持不变
    r = client.patch("/api/profile", json={"auto_tags": False}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "陈老师"

    # 传空串：清空姓名，display_name 回退邮箱前缀
    r = client.patch("/api/profile", json={"name": "  "}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == ""
    assert r.json()["display_name"] == "noname"

    # 再补填生效
    r = client.patch("/api/profile", json={"name": "新名字"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "新名字"
    assert r.json()["display_name"] == "新名字"


def test_profile_patch_phone_round_trip(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "phone@test.example", name="陈老师")
    token = seed_token(db, person, "i" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/profile", json={"name": "陈老师", "phone": "138 0000-0015"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "13800000015"

    r = client.patch("/api/profile", json={"name": "陈老师", "phone": "13900000099"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] == "13900000099"

    r = client.patch("/api/profile", json={"name": "陈老师", "phone": None}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["phone"] is None


def test_profile_name_display_setting(make_client, db):
    """「首页称呼」偏好已下线：一律展示全名，老 payload 里的 name_display 被忽略并清除。"""
    client = make_client(profile.router)
    person = seed_person(db, "display@test.example", name="张毅")
    person.payload = {**(person.payload or {}), "name_display": "teacher"}
    db.commit()
    token = seed_token(db, person, "g" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["display_name"] == "张毅"
    assert "name_display" not in r.json()["settings"]

    r = client.patch(
        "/api/profile",
        json={"name": person.name, "name_display": "teacher"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "张毅"
    assert "name_display" not in r.json()["settings"]
    db.refresh(person)
    assert "name_display" not in person.payload


def test_profile_calendar_birthdays_setting(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "calendar@test.example", name="陈老师")
    token = seed_token(db, person, "h" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch(
        "/api/profile",
        json={"name": person.name, "calendar_birthdays": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["settings"] == {
        "auto_tags": True,
        "calendar_birthdays": False,
    }
    db.refresh(person)
    assert person.payload["calendar_birthdays"] is False


def test_profile_auto_tags_setting(make_client, db):
    client = make_client(profile.router)
    person = seed_person(db, "tags@test.example", name="陈老师")
    token = seed_token(db, person, "f" * 64)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch(
        "/api/profile",
        json={"name": person.name, "auto_tags": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["settings"] == {
        "auto_tags": False,
        "calendar_birthdays": True,
    }
    db.refresh(person)
    assert person.payload["auto_tags"] is False


def test_profile_clear_home_visit_tags(make_client, db):
    import uuid

    from app.models import Tag, person_tags
    from app.routers.students import AUTO_HOME_VISIT_TAG_NAME, _attach_tag_if_missing
    from app.workspace import ensure_workspace_id, tag_student_workspace

    client = make_client(profile.router)
    teacher = seed_person(db, "clear-tags@test.example", name="陈老师")
    ensure_workspace_id(teacher)
    token = seed_token(db, teacher, uuid.uuid4().hex)
    headers = {"Authorization": f"Bearer {token}"}
    mine = seed_person(db, None, role="student", name="林晓雨", admission_no="CLR001")
    other = seed_person(db, None, role="student", name="外班生", admission_no="CLR002")
    tag_student_workspace(mine, teacher)
    _attach_tag_if_missing(db, mine.id, AUTO_HOME_VISIT_TAG_NAME, "#2f7d4f")
    _attach_tag_if_missing(db, other.id, AUTO_HOME_VISIT_TAG_NAME, "#2f7d4f")
    db.commit()

    r = client.post("/api/profile/clear-home-visit-tags", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"removed": 1}
    tag = db.query(Tag).filter(Tag.name == AUTO_HOME_VISIT_TAG_NAME).one()
    assert (
        db.query(person_tags)
        .filter(person_tags.c.person_id == mine.id, person_tags.c.tag_id == tag.id)
        .first()
        is None
    )
    assert (
        db.query(person_tags)
        .filter(person_tags.c.person_id == other.id, person_tags.c.tag_id == tag.id)
        .first()
        is not None
    )


def test_teachers_lists_only_teachers(make_client, db):
    client = make_client(misc.router)
    seed_person(db, "zhang@test.example", name="张老师")
    seed_person(db, "admin@test.example", role="admin", name="管理员")
    seed_person(db, None, role="student", name="林小明", admission_no="S9")
    token = seed_token(db, db.query(Person).filter_by(email="zhang@test.example").one(), "c" * 64)

    r = client.get("/api/teachers", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["name"] for row in rows] == ["张老师"]
    assert set(rows[0]) == {"id", "name", "email"}


# ---------------------------------------------------------------------------
# 修改密码：登录状态下验证当前密码，保留当前会话、踢掉其他会话
# ---------------------------------------------------------------------------

def test_password_change_flow(make_client, db):
    client = _auth_client(make_client)
    seed_person(db, "cp@test.example", name="赵老师")
    db.commit()

    r = client.post("/api/auth/login",
                    json={"email": "cp@test.example", "password": "123456"})
    token = r.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    other = client.post("/api/auth/login",
                        json={"email": "cp@test.example", "password": "123456"}).json()["token"]
    other_headers = {"Authorization": f"Bearer {other}"}

    # 当前密码错误 → 400，密码不变
    r = client.post("/api/auth/password/change", headers=headers,
                    json={"current_password": "wrong!", "new_password": "newpass123"})
    assert r.status_code == 400, r.text
    assert "当前密码" in r.json()["detail"]

    # 新密码过短 → 422
    r = client.post("/api/auth/password/change", headers=headers,
                    json={"current_password": "123456", "new_password": "123"})
    assert r.status_code == 422, r.text

    # 新密码与当前相同 → 400
    r = client.post("/api/auth/password/change", headers=headers,
                    json={"current_password": "123456", "new_password": "123456"})
    assert r.status_code == 400, r.text
    assert "相同" in r.json()["detail"]

    # 未登录 → 401
    assert client.post("/api/auth/password/change",
                       json={"current_password": "123456", "new_password": "newpass123"}
                       ).status_code == 401

    # 正确修改 → 200；当前会话保留，其他会话被踢
    r = client.post("/api/auth/password/change", headers=headers,
                    json={"current_password": "123456", "new_password": "newpass123"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    assert client.get("/api/auth/me", headers=other_headers).status_code == 401

    # 旧密码失效，新密码可登录
    assert client.post("/api/auth/login",
                       json={"email": "cp@test.example", "password": "123456"}).status_code == 401
    r = client.post("/api/auth/login",
                    json={"email": "cp@test.example", "password": "newpass123"})
    assert r.status_code == 200, r.text
