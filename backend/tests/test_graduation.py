"""毕业：班级整体毕业 + 单人毕业；数据保留，列表默认隐藏已毕业。"""
import uuid
from datetime import date

from app.models import Enrollment, Event, Person
from tests.conftest import seed_person, seed_token


def _setup_teacher(db, email):
    from app.workspace import ensure_workspace_id

    teacher = seed_person(db, email, name="王老师")
    ensure_workspace_id(teacher)
    db.commit()
    token = seed_token(db, teacher, uuid.uuid4().hex)
    return teacher, {"Authorization": f"Bearer {token}"}


def _student(client, headers, name):
    r = client.post("/api/students", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _class(client, headers, name):
    r = client.post(
        "/api/classes",
        json={"name": name, "academic_year": "2025/2026"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _enroll(client, headers, student_id, class_id):
    r = client.patch(
        f"/api/students/{student_id}", json={"class_id": class_id}, headers=headers
    )
    assert r.status_code == 200, r.text


def test_graduate_class_archives_and_hides_students(client, db):
    _, headers = _setup_teacher(db, "grad-a@test.example")
    s1 = _student(client, headers, "学生甲")
    s2 = _student(client, headers, "学生乙")
    class_id = _class(client, headers, "毕业班")
    for s in (s1, s2):
        _enroll(client, headers, s["id"], class_id)

    r = client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["graduated"] == 2
    assert r.json()["skipped"] == 0

    # 默认列表隐藏，参数打开可见且带毕业状态/标签/无班级
    r = client.get("/api/students", headers=headers)
    names = [s["name"] for s in r.json()]
    assert "学生甲" not in names and "学生乙" not in names
    r = client.get("/api/students?include_graduated=true", headers=headers)
    by_name = {s["name"]: s for s in r.json()}
    assert by_name["学生甲"]["status"] == "graduated"
    assert "已毕业" in [t["name"] for t in by_name["学生甲"]["tags"]]
    assert by_name["学生甲"]["class"] is None

    # 学籍关闭且 reason=graduated，事件已写
    sid = uuid.UUID(s1["id"])
    assert (
        db.query(Enrollment)
        .filter(Enrollment.person_id == sid, Enrollment.valid_to.is_(None))
        .first()
        is None
    )
    closed = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == sid, Enrollment.reason == "graduated")
        .all()
    )
    assert len(closed) == 1
    event = (
        db.query(Event)
        .filter(Event.type == "graduated", Event.attendees.any(Person.id == sid))
        .one()
    )
    assert event.title == "毕业"

    # 班级归档：默认列表不出现，参数打开带 archived 标记
    r = client.get("/api/classes", headers=headers)
    assert all(c["id"] != class_id for c in r.json())
    r = client.get("/api/classes?include_archived=true", headers=headers)
    archived = [c for c in r.json() if c["id"] == class_id]
    assert archived and archived[0]["archived"] is True

    # 归档班详情名单 = 该班毕业生
    r = client.get(f"/api/classes/{class_id}", headers=headers)
    assert [s["name"] for s in r.json()["students"]] == ["学生甲", "学生乙"]

    # 个人中心毕业归档：已毕业学生 + 归档班级（含毕业生）
    r = client.get("/api/profile", headers=headers)
    body = r.json()
    assert [s["name"] for s in body["graduated_students"]] == ["学生甲", "学生乙"]
    arch = [c for c in body["archived_classes"] if c["id"] == class_id]
    assert arch and [s["name"] for s in arch[0]["students"]] == ["学生甲", "学生乙"]

    # 幂等：毕业后学籍已关闭，名单为空，再毕业无人可处理
    r = client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"graduated": 0, "skipped": 0}


def test_graduate_class_skips_already_graduated(client, db):
    _, headers = _setup_teacher(db, "grad-b@test.example")
    early = _student(client, headers, "提前毕业")
    normal = _student(client, headers, "正常在读")
    class_id = _class(client, headers, "二班")
    for s in (early, normal):
        _enroll(client, headers, s["id"], class_id)
    r = client.patch(
        f"/api/students/{early['id']}", json={"status": "graduated"}, headers=headers
    )
    assert r.status_code == 200, r.text

    r = client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    assert r.status_code == 200, r.text
    # 提前毕业者学籍已关闭，不在班级名单里，不会被重复处理
    assert r.json() == {"graduated": 1, "skipped": 0}
    sid = uuid.UUID(early["id"])
    assert (
        db.query(Event)
        .filter(Event.type == "graduated", Event.attendees.any(Person.id == sid))
        .count()
        == 1
    )


def test_graduate_single_student_and_revert(client, db):
    _, headers = _setup_teacher(db, "grad-c@test.example")
    s = _student(client, headers, "单人毕业")

    r = client.patch(
        f"/api/students/{s['id']}", json={"status": "graduated"}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "graduated"

    # 反悔：改回在读，恢复默认可见；班级需手动重分
    r = client.patch(
        f"/api/students/{s['id']}", json={"status": "active"}, headers=headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    r = client.get("/api/students", headers=headers)
    assert [x["name"] for x in r.json()] == ["单人毕业"]


def test_dashboard_counts_exclude_graduated(client, db):
    _, headers = _setup_teacher(db, "grad-d@test.example")
    s = _student(client, headers, "计数学生")
    class_id = _class(client, headers, "计数班")
    _enroll(client, headers, s["id"], class_id)

    r = client.get("/api/dashboard", headers=headers)
    assert r.json()["counts"]["students"] == 1

    client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    r = client.get("/api/dashboard", headers=headers)
    assert r.json()["counts"]["students"] == 0
    assert r.json()["counts"]["classes"] == 0  # 归档班级不计入


def test_unassigned_class_cannot_graduate(client, db):
    _, headers = _setup_teacher(db, "grad-e@test.example")
    r = client.get("/api/classes", headers=headers)
    unassigned = next(c for c in r.json() if c["is_unassigned"])
    r = client.post(f"/api/classes/{unassigned['id']}/graduate", headers=headers)
    assert r.status_code == 400


def test_graduate_rejects_foreign_class(client, db):
    _, headers = _setup_teacher(db, "grad-f@test.example")
    _, other_headers = _setup_teacher(db, "grad-f-other@test.example")
    foreign_class = _class(client, other_headers, "别班")
    r = client.post(f"/api/classes/{foreign_class}/graduate", headers=headers)
    assert r.status_code == 404


def test_unknown_class_404(client, db):
    _, headers = _setup_teacher(db, "grad-g@test.example")
    r = client.post(f"/api/classes/{uuid.uuid4()}/graduate", headers=headers)
    assert r.status_code == 404


def test_unknown_class_404(client, db):
    _, headers = _setup_teacher(db, "grad-g@test.example")
    r = client.post(f"/api/classes/{uuid.uuid4()}/graduate", headers=headers)
    assert r.status_code == 404


def test_graduated_records_leave_home_and_visits(client, db):
    """毕业归档后：首页摘要、家访页、日历不再出现该生记录；数据保留在档案时间线。"""
    _, headers = _setup_teacher(db, "grad-h@test.example")
    s = _student(client, headers, "小毕业")
    class_id = _class(client, headers, "六2班")
    _enroll(client, headers, s["id"], class_id)

    r = client.post(
        f"/api/students/{s['id']}/events",
        json={"event_type": "home_visited", "summary": "期末家访", "done": True},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    visit_id = r.json()["id"]

    r = client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    assert r.status_code == 200, r.text

    # 首页摘要不再出现该生事件（毕业事件本身也不上首页）
    r = client.get("/api/dashboard", headers=headers)
    recent = r.json()["recent_events"]
    assert all("小毕业" not in [st["name"] for st in ev["students"]] for ev in recent)
    assert all(ev["title"] != "家访" for ev in recent)

    # 家访页不再返回该生记录
    r = client.get("/api/events?type=home_visited", headers=headers)
    assert all(ev["id"] != visit_id for ev in r.json())

    # 日历当月不再有该生的家访/生日记录
    today = date.today()
    r = client.get(f"/api/calendar?year={today.year}&month={today.month}", headers=headers)
    cal = r.json()["items"]
    assert all(item.get("student_id") != s["id"] for item in cal)

    # 数据保留：学生档案时间线仍有家访与毕业记录
    r = client.get(f"/api/students/{s['id']}/timeline", headers=headers)
    types = {e["event_type"] for e in r.json()}
    assert {"home_visited", "graduated"} <= types


def test_graduated_class_exam_becomes_ended(client, db):
    """全部学生参与者毕业 → 考试视为结束：列表打标，首页不再列为即将考试。"""
    _, headers = _setup_teacher(db, "grad-i@test.example")
    s = _student(client, headers, "参考学生")
    class_id = _class(client, headers, "六3班")
    _enroll(client, headers, s["id"], class_id)

    r = client.post("/api/exams", json={
        "name": "期末统考", "exam_date": "2027-06-20",
        "subjects": [{"subject": "math", "full_score": 100}],
        "class_ids": [class_id],
    }, headers=headers)
    assert r.status_code == 201, r.text
    exam_id = r.json()["id"]

    def flag():
        r = client.get("/api/exams", headers=headers)
        return next(e for e in r.json() if e["id"] == exam_id)

    assert flag()["students_graduated"] is False

    r = client.post(f"/api/classes/{class_id}/graduate", headers=headers)
    assert r.status_code == 200, r.text
    assert flag()["students_graduated"] is True

    r = client.get("/api/dashboard", headers=headers)
    assert all(e["id"] != exam_id for e in r.json()["upcoming_exams"])
