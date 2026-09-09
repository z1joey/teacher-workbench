"""Seed smoke tests on the event schema.

`app.seed.run()` against a throwaway SQLite database (DATABASE_URL env +
fresh `app.*` import, like the pre-migration test did) must load the demo
content the frontend stories rely on: role counts, the event-type census
(six graded sittings × nine subjects × 24 students, the correction story,
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
    assert r.json() == {"ok": True, "version": "0.1.0", "beta": True}


def test_seed_loads_demo_data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'seed.db'}")
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
        # roles: 1 admin + 1 teacher (the sole 班主任) + 24 students + 25 guardians (王秀英
        # is shared by 王浩 and 邓晓彤, so 24 primary + 1 shared)
        role_of = Person.payload["role"].as_string()
        roles = dict(db.query(role_of, func.count(Person.id)).group_by(role_of).all())
        assert roles == {"admin": 1, "teacher": 1, "student": 24, "guardian": 25}

        # guardian scenarios: 王浩 has two guardians; 王秀英 covers two students
        wang = db.query(Person).filter(Person.name == "王浩").one()
        assert len(wang.guardians) == 2
        grandmah = next(g for g in wang.guardians if g.name == "王秀英")
        assert len(grandmah.students) == 2
        assert {s.name for s in grandmah.students} == {"王浩", "邓晓彤"}

        # events by type: 6 graded sittings + 1 upcoming exam, every
        # student-subject of the graded sittings scored, 3 correction stories,
        # 王浩's class move, 5 visits (one planned), 2 notes, teacher-written
        # records (评语/谈话/辅导/电话沟通), 比赛/活动, plus yearly birthdays.
        types = dict(db.query(Event.type, func.count(Event.id)).group_by(Event.type).all())
        assert types == {
            "exam": 7,
            "score": 6 * 9 * 24,
            "enrolled": 24,
            "class_moved": 1,
            "home_visited": 5,
            "note_added": 2,
            "result_changed": 3,
            "comment": 3,
            "talk": 2,
            "tutoring": 3,
            "parent_call": 2,
            "activity": 4,
            "seat_changed": 24,
            "birthday": 24,
        }

        # every home visit carries a purpose; exactly one stays 未完成 so the
        # 待跟进 queue is non-empty
        visit_payloads = [
            p for (p,) in db.query(Event.payload).filter(Event.type == "home_visited").all()
        ]
        assert all(p.get("purpose") for p in visit_payloads)
        assert sum(1 for p in visit_payloads if not p.get("done")) == 1

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

        # enrollments: 24 admitted + 王浩's 七2→七1 move
        assert db.query(Enrollment).count() == 25
        moved = db.query(Enrollment).filter(Enrollment.reason == "moved").all()
        assert len(moved) == 1

        # tags: 2 demo tags, each attached to exactly 2 students
        tags = db.query(Tag).all()
        assert {t.name for t in tags} == {"需关注", "课代表"}
        usage = dict(
            db.query(Tag.name, func.count(person_tags.c.person_id))
            .outerjoin(person_tags, person_tags.c.tag_id == Tag.id)
            .group_by(Tag.id)
            .all()
        )
        assert usage == {"需关注": 2, "课代表": 2}

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

        # every active student with birth_date gets one system birthday Event
        birth_dates = (
            db.query(Person.payload["birth_date"].as_string())
            .filter(role_of == "student")
            .all()
        )
        assert len(birth_dates) == 24
        for (iso,) in birth_dates:
            date.fromisoformat(iso)  # raises on a non-ISO value
    finally:
        db.close()
        engine.dispose()
