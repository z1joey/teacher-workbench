"""Create tables and load demo data. Run from backend/: python -m app.seed

Demo content is Chinese-only: names, visits and notes are stored as plain text.

Event-centric schema: a person carries role + profile in a registry-validated
payload (app.payloads); `name` is a typed person column and a student's
guardians are Person rows of role "guardian" linked through student_guardians
(not flattened onto the student payload). Exam sittings are Event(type="exam")
rows with the per-subject full scores in payload["full_scores"], scores are
per-student score Events titled "<exam name>·<subject>", and the manual
timeline (visits, notes) is written through app.eventing.create_event.
Class/Enrollment keep current membership; tags attach to persons. Birthdays
are NOT persisted — the timeline projects them from payload["birth_date"].

Re-seeding an existing database duplicates the demo data — remove the SQLite
file (or drop the schema) first.
"""
import random
import uuid
from datetime import date, datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .unassigned import ensure_unassigned_class
from .eventing import create_event
from .models import Class, Enrollment, Event, Person, Tag, student_guardians
from .payloads import validate_person_payload
from .routers.students import _guardians_of, _find_or_create_guardian
from .security import hash_password

random.seed(2026)

ACADEMIC_YEAR = "2025/2026"
ENROLL_DATE = date(2025, 9, 1)

# 初中全科：科目 key 与满分（语数英 120，其余 100），颜色与前端目录一致
SUBJECT_FULL_SCORES = {
    "chinese": 120.0, "math": 120.0, "english": 120.0,
    "politics": 100.0, "history": 100.0, "geography": 100.0,
    "biology": 100.0, "physics": 100.0, "chemistry": 100.0,
}
SUBJECT_COLORS = {
    "chinese": "#b98a2e", "math": "#2e6ba8", "english": "#2f7d4f",
    "politics": "#c2608f", "history": "#8c564b", "geography": "#2b8a8a",
    "biology": "#5a8f29", "physics": "#6d5bb8", "chemistry": "#b42318",
}
ALL_SUBJECTS = list(SUBJECT_FULL_SCORES)

# (name, gender)
NAMES_7_1 = [
    ("林晓雨", "F"), ("陈佳怡", "F"), ("周子涵", "M"), ("吴一凡", "M"), ("徐曼怡", "F"),
    ("高子辰", "M"), ("宋雅轩", "F"), ("韩如冰", "F"), ("乔安琪", "F"), ("冯俊豪", "M"),
    ("唐美琳", "F"), ("罗蔚一", "M"),
]
NAMES_7_2 = [
    ("王浩", "M"), ("李思彤", "F"), ("张悦", "M"), ("刘宇宸", "M"), ("郭浩然", "M"),
    ("何佳欣", "F"), ("崔明轩", "M"), ("潘书涵", "F"), ("袁志远", "M"), ("邓晓彤", "F"),
    ("任凯文", "M"), ("沈洛一", "M"),
]

EXAM_HOUR = time(9, 0)  # sittings and their score rows are dated the exam day 09:00


def dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def seed(db: Session, *, teacher: Person | None = None, include_admin: bool = True) -> Person:
    """Load demo school data.

    When `teacher` is supplied (in-app demo load), demo classes and records bind
    to that account. CLI seed creates the fixed demo teacher/admin accounts.
    """
    if teacher is None:
        if include_admin:
            admin = Person(name="开发者", phone="13800000000", email="admin@school.dev",
                           password_hash=hash_password("admin123"),
                           payload=validate_person_payload("admin", {}))
            db.add(admin)
        teacher = Person(name="陈老师", phone="13800000001", email="chen@school.edu",
                         password_hash=hash_password("123456"),
                         payload=validate_person_payload("teacher", {}))
        db.add(teacher)
        db.flush()
    c71 = Class(name="七年级1班", academic_year=ACADEMIC_YEAR)
    c72 = Class(name="七年级2班", academic_year=ACADEMIC_YEAR)
    db.add_all([c71, c72])
    db.flush()

    # A full school year of assessments so score trends have shape:
    # six scored exams plus one upcoming (not yet graded, no scores).
    EXAM_PLAN = [
        ("oct", "10月月考", date(2025, 10, 15)),
        ("premid", "期中考试", date(2025, 11, 18)),
        ("prefinal", "期末考试", date(2026, 1, 22)),
        ("mar", "3月月考", date(2026, 3, 17)),
        ("midterm", "期中考试", date(2026, 4, 15)),
        ("final", "期末考试", date(2026, 6, 25)),
        ("next", "期中考试", date(2026, 9, 17)),  # upcoming — no scores
    ]

    # --- students + enrollment -------------------------------------------
    students: list[Person] = []

    def make_students(names: list[tuple[str, str]], cls: Class, start_no: int) -> None:
        for i, (name, gender) in enumerate(names):
            payload = validate_person_payload("student", {
                "admission_no": f"S2025{start_no + i:03d}",
                "gender": gender,
                "birth_date": date(2012, random.randint(1, 12), random.randint(1, 28)).isoformat(),
                "address": f"解放路{100 + i}号",
            })
            s = Person(name=name, password_hash=hash_password(uuid.uuid4().hex),
                       payload=payload)
            db.add(s)
            db.flush()
            # guardian of record: an independent Person linked via student_guardians
            guardian = _find_or_create_guardian(
                db, f"{name[0]}女士", f"139{random.randint(10_000_000, 99_999_999)}"
            )
            db.execute(student_guardians.insert().values(
                student_id=s.id, guardian_id=guardian.id
            ))
            db.add(Enrollment(person_id=s.id, class_id=cls.id,
                              valid_from=ENROLL_DATE, reason="admitted"))
            create_event(db, event_type="enrolled", title="入学",
                         start_time=dt(ENROLL_DATE, time(8, 0)),
                         payload={"class_name": cls.name}, attendee_ids=[s.id])
            students.append(s)

    make_students(NAMES_7_1, c71, 1)
    make_students(NAMES_7_2, c72, 101)
    db.flush()

    # guardian scenarios: 王浩 has two guardians, and 王秀英 is shared by
    # 王浩 (祖母) and 邓晓彤 (外祖母) — same name/phone merges into one Person
    by_name = {s.name: s for s in students}
    wang, deng = by_name["王浩"], by_name["邓晓彤"]
    grandmah = _find_or_create_guardian(db, "王秀英", "13900000000",
                                        address="解放路108号")
    db.execute(student_guardians.insert().values(
        student_id=wang.id, guardian_id=grandmah.id, relationship="祖母"))
    db.execute(student_guardians.insert().values(
        student_id=deng.id, guardian_id=grandmah.id, relationship="外祖母"))
    db.flush()

    # demo tags (globally reusable once attached)
    focus_tag = Tag(name="需关注", color="#b42318")
    rep_tag = Tag(name="课代表", color="#177245")
    db.add_all([focus_tag, rep_tag])
    db.flush()
    for tag, names in ((focus_tag, ["林晓雨", "王浩"]), (rep_tag, ["宋雅轩", "郭浩然"])):
        for n in names:
            s = by_name.get(n)
            if s:
                tag.people.append(s)
    db.flush()

    # --- exam sittings: one Event(type="exam") each; the per-subject full
    # score config rides in payload["full_scores"] (the score-entry flow reads
    # it to set each score payload's max_score). School-wide sitting, so the
    # whole active student body plus the homeroom teacher attends.
    exams_by_key: dict[str, Event] = {}
    for exam_key, exam_name, exam_date in EXAM_PLAN:
        exams_by_key[exam_key] = create_event(
            db, event_type="exam", title=exam_name,
            start_time=dt(exam_date, EXAM_HOUR),
            payload={"full_scores": dict(SUBJECT_FULL_SCORES),
                     "subject_colors": dict(SUBJECT_COLORS)},
            attendee_ids=[teacher.id, *[s.id for s in students]],
        )
    db.flush()

    # --- subject-level ability + scores (per-student score Events) --------
    # 语言类（语/英）与理科类（数/物/化）各共享一个能力因子，其余科目独立
    ability = {}
    for s in students:
        verbal = random.gauss(70, 10)
        science = random.gauss(72, 12)
        ability[s.id] = {
            "chinese": verbal + random.gauss(0, 4),
            "english": verbal + random.gauss(0, 4),
            "math": science + random.gauss(0, 4),
            "physics": science + random.gauss(0, 4),
            "chemistry": science + random.gauss(0, 4),
            "politics": random.gauss(75, 8),
            "history": random.gauss(72, 9),
            "geography": random.gauss(70, 10),
            "biology": random.gauss(71, 9),
        }
    # Story: 林晓雨数学偏弱，王浩数学方程部分薄弱（表现为 math 能力下调）。
    lin = next(s for s in students if s.name == "林晓雨")
    hao = next(s for s in students if s.name == "王浩")
    guo = next(s for s in students if s.name == "郭浩然")
    ability[lin.id]["math"] = 58.0
    ability[hao.id]["math"] = 62.0

    # Trends so the per-subject lines tell a story: a gentle class-wide rise
    # across the year plus a per-student slope. 王浩 dips during his 频繁迟到
    # stretch (before the 2026-03-01 class move + home visit), then recovers.
    SCORED_EXAMS = ["oct", "premid", "prefinal", "mar", "midterm", "final"]
    exam_trend = {"oct": 0.0, "premid": 1.0, "prefinal": 1.5,
                  "mar": 2.0, "midterm": 3.0, "final": 4.0}
    slope = {
        s.id: {sub: random.uniform(-2.0, 2.6) for sub in ALL_SUBJECTS}
        for s in students
    }
    slope[lin.id]["math"] = 2.8      # weak start, climbing all year (提升计划)
    slope[guo.id]["english"] = 3.0   # steady english riser
    slope[hao.id]["math"] = 0.8
    hao_dip = {"premid": -6.5, "prefinal": -5.5, "mar": -2.0}  # attendance slump

    # a few absences to complete the slump story: 王浩 misses one subject at
    # two sittings, 林晓雨 sits out politics in March (absent convention:
    # absent=true, no score key)
    ABSENCES = {
        (hao.id, "premid", "geography"),
        (hao.id, "prefinal", "biology"),
        (lin.id, "mar", "politics"),
    }

    lin_math_old: float | None = None
    lin_math_new: float | None = None

    for exam_key in SCORED_EXAMS:
        exam = exams_by_key[exam_key]
        for subject in ALL_SUBJECTS:
            for s in students:
                base = (
                    ability[s.id][subject]
                    + exam_trend[exam_key]
                    + slope[s.id][subject] * SCORED_EXAMS.index(exam_key)
                    + random.gauss(0, 3.0)
                )
                if s.id == hao.id and subject == "math":
                    base += hao_dip.get(exam_key, 0.0)
                score = round(clamp(base, 0.0, SUBJECT_FULL_SCORES[subject]), 1)
                payload: dict = {"subject": subject,
                                 "max_score": SUBJECT_FULL_SCORES[subject]}
                if (s.id, exam_key, subject) in ABSENCES:
                    payload["absent"] = True
                else:
                    # story: 陈老师 corrects an addition error on 林晓雨's
                    # midterm math score (+5) — the score Event carries the
                    # corrected value; a result_changed Event documents it.
                    if (s.id, exam_key, subject) == (lin.id, "midterm", "math"):
                        lin_math_old = score
                        score = round(clamp(score + 5.0, 0.0, SUBJECT_FULL_SCORES["math"]), 1)
                        lin_math_new = score
                    payload["score"] = score
                create_event(db, event_type="score",
                             title=f"{exam.title}·{subject}",
                             start_time=dt(exam.start_time.date(), EXAM_HOUR),
                             payload=payload, attendee_ids=[s.id])
    db.flush()

    create_event(db, event_type="result_changed", title="math成绩更正",
                 start_time=dt(date(2026, 4, 16), time(16, 30)),
                 payload={"exam": exams_by_key["midterm"].title,
                          "subject": "math", "old": lin_math_old, "new": lin_math_new,
                          "reason": "评分册登记错误更正"},
                 attendee_ids=[lin.id])

    # story: 王浩 moves 七年级2班 -> 七年级1班 on 2026-03-01 (spring semester;
    # his 3月月考 onwards are recorded with the new class)
    old_enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == hao.id, Enrollment.class_id == c72.id)
        .first()
    )
    old_enrollment.valid_to = date(2026, 3, 1)
    db.flush()
    db.add(Enrollment(person_id=hao.id, class_id=c71.id,
                      valid_from=date(2026, 3, 1), reason="moved"))
    db.flush()
    create_event(db, event_type="class_moved", title="转班",
                 start_time=dt(date(2026, 3, 1), time(8, 30)),
                 payload={"from_class": c72.name,
                          "to_class": c71.name,
                          "reason": "均衡编班"},
                 attendee_ids=[hao.id])

    # --- home visits + notes -------------------------------------------------
    # Visits involve 陈老师 (the visiting teacher), the student and the
    # guardian of record (snapshotted from the linked guardian Person); notes
    # involve her and the student. Home-visit purpose folds into the summary
    # (HomeVisitPayload has summary/purpose/guardian only).
    visits = [
        (hao, datetime(2026, 3, 20, 19, 0),
         "频繁迟到：父母上早班，商定由爷爷负责早餐和晨间作息。"),
        (lin, datetime(2026, 5, 10, 19, 30),
         "数学提升计划：与家长沟通分数专项练习计划，每周二、周四各练习20分钟。"),
        (guo, datetime(2026, 6, 5, 18, 30),
         "期末走访：家庭支持到位，学生自述备考状态良好。"),
    ]
    for student, when, summary in visits:
        guardians = _guardians_of(db, student.id)
        create_event(db, event_type="home_visited", title="家访", start_time=when,
                     payload={"summary": summary,
                              "guardian": guardians[0][0].name if guardians else None},
                     attendee_ids=[student.id, teacher.id])

    create_event(db, event_type="note_added", title="随笔",
                 start_time=datetime(2026, 4, 20, 15, 0),
                 payload={"notes": "对多步骤分数应用题掌握不牢，建议用画图法辅助理解。"},
                 attendee_ids=[lin.id, teacher.id])
    create_event(db, event_type="note_added", title="随笔",
                 start_time=datetime(2026, 3, 22, 15, 0),
                 payload={"notes": "家庭约定后，出勤情况明显改善。"},
                 attendee_ids=[hao.id, teacher.id])

    return teacher


def run() -> None:
    # Alembic 0005 (event schema) is the path for existing PostgreSQL databases;
    # fresh databases are created + seeded here.
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        ensure_unassigned_class(db)
        db.commit()
        seed(db)
        db.commit()
        role_of = Person.payload["role"].as_string()
        roles = dict(db.query(role_of, func.count(Person.id)).group_by(role_of).all())
        types = dict(db.query(Event.type, func.count(Event.id)).group_by(Event.type).all())
        print("Seed complete:")
        print(f"  persons by role: {roles}")
        print(f"  events by type: {types}")
        print(f"  tags: {db.query(Tag).count()}")
        print(f"  enrollments: {db.query(Enrollment).count()}")
        print("  demo login: 13800000001 / 123456")
        print("  admin login: 13800000000 / admin123  → hidden /admin dashboard")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
