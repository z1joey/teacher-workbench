"""Seed smoke tests on the event schema.

`app.seed.run()` against a throwaway SQLite database (DATABASE_URL env +
fresh `app.*` import, like the pre-migration test did) must load the demo
content the frontend stories rely on: role counts, the event-type census
(six graded sittings × nine subjects × 24 students,
王浩's class move, visits + notes), tag usage, enrollments, working seeded
logins, the "<exam>·<subject>" score-title convention, and the projected-
birthday precondition — students carry an ISO birth_date in the payload and
no birthday Event is ever persisted.

`test_full_app_client_smoke` proves the conftest full-app `client` fixture
(real app.main, test engine) boots and serves.
"""
import sys
from datetime import date


def test_full_app_client_smoke(client):
    # The conftest `client` fixture: the real app.main app, get_db on the
    # per-test engine — boots and serves the no-auth health route.
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": "0.1.1", "beta": True}


def test_seed_loads_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'seed.db'}")
    # 隔离开发者 .env 里的 ADMIN_*：本测试断言的是演示默认账密
    monkeypatch.setenv("ADMIN_EMAIL", "admin@school.dev")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin123")
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]

    from app import seed as seed_mod

    seed_mod.run()

    from sqlalchemy import func

    from app.database import SessionLocal, engine
    from app.models import Enrollment, Event, Person, Tag, person_tags
    from app.security import verify_password

    db = SessionLocal()
    try:
        # roles: 1 admin + 1 teacher (the sole 班主任) + 30 students (24 active
        # + 6 graduated 六1班) + 31 guardians (王秀英 is shared by 王浩 and
        # 邓晓彤, so 30 primary + 1 shared)
        role_of = Person.payload["role"].as_string()
        roles = dict(db.query(role_of, func.count(Person.id)).group_by(role_of).all())
        assert roles == {"admin": 1, "teacher": 1, "student": 30, "guardian": 31}

        # guardian scenarios: 王浩 has two guardians; 王秀英 covers two students
        wang = db.query(Person).filter(Person.name == "王浩").one()
        assert len(wang.guardians) == 2
        grandmah = next(g for g in wang.guardians if g.name == "王秀英")
        assert len(grandmah.students) == 2
        assert {s.name for s in grandmah.students} == {"王浩", "邓晓彤"}

        # events by type: 6 graded sittings + 1 upcoming exam, every
        # student-subject of the graded sittings scored,
        # 王浩's class move, 15 visits (six planned), 2 notes, teacher-written
        # records (评语/家访), plus yearly birthdays — and the graduation
        # story: 6 入学 + 6 毕业 events for 六1班.
        types = dict(db.query(Event.type, func.count(Event.id)).group_by(Event.type).all())
        assert types == {
            "exam": 7,
            "score": 6 * 9 * 24,
            "enrolled": 30,
            "class_moved": 1,
            "graduated": 6,
            "home_visited": 15,
            "comment": 20,
            "summary": 7,
            "seat_changed": 24,
            "birthday": 24,
        }

        # every home visit carries a purpose; several stay 未完成 so the
        # 待跟进 queue is non-empty
        visit_payloads = [
            p for (p,) in db.query(Event.payload).filter(Event.type == "home_visited").all()
        ]
        assert all(p.get("purpose") for p in visit_payloads)
        assert sum(1 for p in visit_payloads if not p.get("done")) == 6

        # seating: both classes ship a persisted layout; 王浩 (moved to 七1)
        # keeps a seat there, and one class has empty seats for realism
        from app.models import Class, ClassSeating

        seatings = {s.class_id: s for s in db.query(ClassSeating).all()}
        assert len(seatings) == 2
        c71_seating = next(
            s for s in seatings.values()
            if db.get(Class, s.class_id).name == "七年级1班"
        )
        assert (c71_seating.rows, c71_seating.cols) == (4, 4)
        assert len(c71_seating.seats) == 13
        assert str(wang.id) in c71_seating.seats.values()

        # absent convention: absent=true with no score key
        payloads = [p for (p,) in db.query(Event.payload).filter(Event.type == "score").all()]
        absent = [p for p in payloads if p.get("absent")]
        graded = [p for p in payloads if not p.get("absent")]
        assert len(absent) == 3
        assert all("score" not in p for p in absent)
        assert len(graded) == 6 * 9 * 24 - 3
        assert all(isinstance(p.get("score"), (int, float)) and p.get("max_score") for p in graded)

        # score-title convention: "<exam name>·<subject key>" — 期中考试 sits
        # twice (Nov + Apr), each sitting scores all 24 students in math
        midterm_math = (
            db.query(func.count(Event.id))
            .filter(Event.type == "score", Event.title == "期中考试·math")
            .scalar()
        )
        assert midterm_math == 2 * 24

        # enrollments: 24 admitted + 王浩's 七2→七1 move + 6 closed 六1班 rows
        assert db.query(Enrollment).count() == 31
        moved = db.query(Enrollment).filter(Enrollment.reason == "moved").all()
        assert len(moved) == 1

        # tags: 2 manual demo tags + 已家访 auto-applied for completed visits
        # + 已毕业 for the graduated 六1班 cohort
        tags = db.query(Tag).all()
        assert {t.name for t in tags} == {"需关注", "课代表", "已家访", "已毕业"}
        usage = dict(
            db.query(Tag.name, func.count(person_tags.c.person_id))
            .outerjoin(person_tags, person_tags.c.tag_id == Tag.id)
            .group_by(Tag.id)
            .all()
        )
        assert usage["需关注"] == 2
        assert usage["课代表"] == 2
        done_visit_students = set()
        for ev in db.query(Event).filter(Event.type == "home_visited").all():
            if (ev.payload or {}).get("done"):
                for person in ev.attendees:
                    if (person.payload or {}).get("role") == "student":
                        done_visit_students.add(person.id)
        visit_tag = next(t for t in tags if t.name == "已家访")
        tagged = {
            row[0]
            for row in db.query(person_tags.c.person_id)
            .filter(person_tags.c.tag_id == visit_tag.id)
            .all()
        }
        assert tagged == done_visit_students
        assert usage["已家访"] == len(done_visit_students) == 9
        grad_tag = next(t for t in tags if t.name == "已毕业")
        assert usage["已毕业"] == 6

        # graduation: 六1班 is archived; its 6 students carry graduated_at +
        # graduated_at set and their 六1班 enrollment closed on the grad date
        c71 = db.query(Class).filter(Class.name == "七年级1班").one()
        assert c71.academic_year == "2025-09"
        c61 = db.query(Class).filter(Class.name == "六1班").one()
        assert c61.academic_year == "2024-09"
        assert c61.archived is True
        grad_at = Person.payload["graduated_at"].as_string()
        grads = (
            db.query(Person)
            .join(Enrollment, Enrollment.person_id == Person.id)
            .filter(
                Enrollment.class_id == c61.id,
                grad_at.is_not(None),
            )
            .distinct()
            .all()
        )
        assert {s.name for s in grads} == {n for n, _ in [
            ("赵一诺", "F"), ("钱思远", "M"), ("孙悦宁", "F"),
            ("黄嘉树", "M"), ("范雨桐", "F"), ("魏子墨", "M"),
        ]}
        assert all((s.payload or {}).get("graduated_at") for s in grads)
        closed = (
            db.query(Enrollment)
            .filter(Enrollment.class_id == c61.id, Enrollment.valid_to.is_not(None))
            .all()
        )
        assert len(closed) == 6
        assert all(e.valid_from == date(2024, 9, 1) and e.valid_to == date(2025, 7, 4) for e in closed)

        # seeded logins verify: admin/admin123, 陈老师/123456 — and the hashes
        # are not interchangeable
        admin = db.query(Person).filter(Person.phone == "13800000000").one()
        chen = db.query(Person).filter(Person.phone == "13800000001").one()
        assert admin.role == "admin" and chen.role == "teacher"
        # `name` is a typed person column — it is not part of the payload
        assert chen.name == "陈老师"
        assert verify_password("admin123", admin.password_hash)
        assert verify_password("123456", chen.password_hash)
        assert not verify_password("admin123", chen.password_hash)

        # 录入成绩统计：score 事件同时挂录入老师（教学足迹「录入成绩」）
        chen_scores = (
            db.query(func.count(Event.id))
            .filter(Event.type == "score", Event.attendees.any(Person.id == chen.id))
            .scalar()
        )
        assert chen_scores == 6 * 9 * 24

        # every student with birth_date carries an ISO birth_date (30 = 24
        # active + 6 graduated; birthday Events are only projected for active)
        birth_dates = (
            db.query(Person.payload["birth_date"].as_string())
            .filter(role_of == "student")
            .all()
        )
        assert len(birth_dates) == 30
        for (iso,) in birth_dates:
            date.fromisoformat(iso)  # raises on a non-ISO value
    finally:
        db.close()
        engine.dispose()
