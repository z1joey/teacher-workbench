"""Create tables and load demo data. Run from backend/: python -m app.seed

Demo content is Chinese-only: names, visits and notes are stored as plain text.

Note (2026-09): KnowledgePoint / Question / QuestionResponse / StudentWeakness
tables have been REMOVED. Exam scores are generated directly at the subject
level (ExamResult row per student per exam subject).
"""
import random
from datetime import date, datetime, time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from .database import SessionLocal, engine
from .events import add_event, next_birthday_date
from .models import (
    StudentTag,
    Tag,
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    Student,
    StudentEvent,
    TeacherProfile,
    User,
)
from .security import hash_password

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


random.seed(2026)

ACADEMIC_YEAR = "2025/2026"
ENROLL_DATE = date(2025, 9, 1)

SUBJECT_FULL_SCORE = 100.0

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


def dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def seed(db: Session) -> None:
    admin = User(name="开发者", email="admin@school.dev", phone="13800000000",
                 password_hash=hash_password("admin123"), role="admin")
    chen = User(name="陈老师", email="chen@school.edu", phone="13800000001",
                password_hash=hash_password("123456"), role="teacher")
    zhao = User(name="赵老师", email="zhao@school.edu", phone="13800000002",
                password_hash=hash_password("123456"), role="teacher")
    db.add_all([admin, chen, zhao])
    db.flush()
    db.add_all([
        TeacherProfile(user_id=chen.id, subject="math"),
        TeacherProfile(user_id=zhao.id, subject="english"),
    ])
    db.flush()

    c71 = Class(name="七年级1班", grade_level=7,
                academic_year=ACADEMIC_YEAR, homeroom_teacher_id=chen.id)
    c72 = Class(name="七年级2班", grade_level=7,
                academic_year=ACADEMIC_YEAR, homeroom_teacher_id=zhao.id)
    db.add_all([c71, c72])
    db.flush()

    # A full school year of assessments so score trends have shape:
    # six scored exams plus one upcoming (not yet graded, no results).
    EXAM_PLAN = [
        ("oct", "10月月考", date(2025, 10, 15)),
        ("premid", "期中考试", date(2025, 11, 18)),
        ("prefinal", "期末考试", date(2026, 1, 22)),
        ("mar", "3月月考", date(2026, 3, 17)),
        ("midterm", "期中考试", date(2026, 4, 15)),
        ("final", "期末考试", date(2026, 6, 25)),
        ("next", "期中考试", date(2026, 9, 17)),  # upcoming — no results
    ]
    exams_by_key: dict[str, Exam] = {}
    for exam_key, exam_name, exam_date in EXAM_PLAN:
        exam = Exam(name=exam_name, exam_date=exam_date)
        db.add(exam)
        db.flush()
        exams_by_key[exam_key] = exam
    midterm, final = exams_by_key["midterm"], exams_by_key["final"]

    exam_subject_by_key: dict[tuple[str, str], ExamSubject] = {}
    for exam_key, exam in exams_by_key.items():
        for subject in ("math", "english"):
            es = ExamSubject(exam_id=exam.id, subject=subject, full_score=SUBJECT_FULL_SCORE)
            db.add(es)
            exam_subject_by_key[(exam_key, subject)] = es
    db.flush()

    # --- students + enrollment -------------------------------------------
    students: list[Student] = []

    def make_students(names: list[tuple[str, str]], cls: Class, start_no: int) -> None:
        for i, (name, gender) in enumerate(names):
            s = Student(
                admission_no=f"S2025{start_no + i:03d}",
                name=name,
                gender=gender,
                birth_date=date(2012, random.randint(1, 12), random.randint(1, 28)),
                guardian_name=f"{name[0]}女士",
                guardian_phone=f"139{random.randint(10_000_000, 99_999_999)}",
                address=f"解放路{100 + i}号",
            )
            db.add(s)
            db.flush()
            db.add(Enrollment(student_id=s.id, class_id=cls.id,
                              valid_from=ENROLL_DATE, reason="admitted"))
            add_event(db, s.id, "enrolled", dt(ENROLL_DATE, time(8, 0)),
                      actor_teacher_id=cls.homeroom_teacher_id,
                      payload={"class": cls.name})
            students.append(s)

    make_students(NAMES_7_1, c71, 1)
    make_students(NAMES_7_2, c72, 101)
    db.flush()

    # demo tags (globally reusable once attached)
    focus_tag = Tag(name="需关注", color="#b42318")
    rep_tag = Tag(name="课代表", color="#177245")
    db.add_all([focus_tag, rep_tag])
    db.flush()
    by_name = {s.name: s for s in students}
    for tag_name, names in (("需关注", ["林晓雨", "王浩"]), ("课代表", ["宋雅轩", "郭浩然"])):
        tag = focus_tag if tag_name == "需关注" else rep_tag
        for n in names:
            s = by_name.get(n)
            if s:
                db.add(StudentTag(student_id=s.id, tag_id=tag.id))
    db.flush()

    # recurring birthday events (auto-created on real signups too)
    for s in students:
        if not s.birth_date:
            continue
        bday = next_birthday_date(s.birth_date)
        add_event(db, s.id, "birthday", dt(bday, time(9, 0)),
                  recurrence="yearly",
                  payload={"birth_date": s.birth_date.isoformat()})
    db.flush()

    lin = next(s for s in students if s.name == "林晓雨")
    hao = next(s for s in students if s.name == "王浩")
    guo = next(s for s in students if s.name == "郭浩然")

    # --- subject-level ability + results (no per-question detail) --------
    ability = {
        s.id: {"math": random.gauss(72, 12), "english": random.gauss(70, 13)}
        for s in students
    }
    # Story: 林晓雨数学偏弱，王浩数学方程部分薄弱（表现为 math 能力下调）。
    ability[lin.id]["math"] = 58.0
    ability[hao.id]["math"] = 62.0

    # Trends so the per-subject lines tell a story: a gentle class-wide rise
    # across the year plus a per-student slope. 王浩 dips during his 频繁迟到
    # stretch (before the 2026-03-01 class move + home visit), then recovers.
    SCORED_EXAMS = ["oct", "premid", "prefinal", "mar", "midterm", "final"]
    exam_trend = {"oct": 0.0, "premid": 1.0, "prefinal": 1.5,
                  "mar": 2.0, "midterm": 3.0, "final": 4.0}
    slope = {
        s.id: {"math": random.uniform(-2.0, 2.6), "english": random.uniform(-2.0, 2.6)}
        for s in students
    }
    slope[lin.id]["math"] = 2.8      # weak start, climbing all year (提升计划)
    slope[guo.id]["english"] = 3.0   # steady english riser
    slope[hao.id]["math"] = 0.8
    hao_dip = {"premid": -6.5, "prefinal": -5.5, "mar": -2.0}  # attendance slump

    result_by_key: dict[tuple[int, str, str], ExamResult] = {}

    for exam_key in SCORED_EXAMS:
        exam = exams_by_key[exam_key]
        for subject in ("math", "english"):
            es = exam_subject_by_key[(exam_key, subject)]
            entering_teacher = chen if subject == "math" else zhao
            for s in students:
                base = (
                    ability[s.id][subject]
                    + exam_trend[exam_key]
                    + slope[s.id][subject] * SCORED_EXAMS.index(exam_key)
                    + random.gauss(0, 3.0)
                )
                if s.id == hao.id and subject == "math":
                    base += hao_dip.get(exam_key, 0.0)
                score = round(clamp(base, 0.0, SUBJECT_FULL_SCORE), 1)
                result = ExamResult(
                    student_id=s.id, exam_subject_id=es.id,
                    score=score, status="entered",
                    entered_by=entering_teacher.id,
                )
                db.add(result)
                db.flush()
                result_by_key[(s.id, exam_key, subject)] = result

    # story: 陈老师 corrects an addition error on 林晓雨's midterm math score
    # (+5 points, still ≤ 100).
    lin_math_midterm = result_by_key[(lin.id, "midterm", "math")]
    old_score = lin_math_midterm.score
    lin_math_midterm.score = round(clamp(old_score + 5.0, 0.0, SUBJECT_FULL_SCORE), 1)
    add_event(db, lin.id, "result_changed", dt(date(2026, 4, 16), time(16, 30)),
              actor_teacher_id=chen.id, ref_table="exam_result",
              ref_id=lin_math_midterm.id,
              payload={"exam": midterm.name,
                       "subject": "math", "old": old_score, "new": lin_math_midterm.score,
                       "reason": "评分册登记错误更正"})

    # story: 王浩 moves 七年级2班 -> 七年级1班 on 2026-03-01 (spring semester;
    # his 3月月考 onwards are recorded with the new class)
    old_enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == hao.id, Enrollment.class_id == c72.id)
        .first()
    )
    old_enrollment.valid_to = date(2026, 3, 1)
    db.flush()
    db.add(Enrollment(student_id=hao.id, class_id=c71.id,
                      valid_from=date(2026, 3, 1), reason="moved"))
    db.flush()
    add_event(db, hao.id, "class_moved", dt(date(2026, 3, 1), time(8, 30)),
              actor_teacher_id=chen.id,
              payload={"from": c72.name,
                       "to": c71.name,
                       "reason": "均衡编班"})

    # --- timeline: exam events (subject scores) ---------------------------
    for exam_key in SCORED_EXAMS:
        exam = exams_by_key[exam_key]
        for s in students:
            scores = {
                subject: result_by_key[(s.id, exam_key, subject)].score
                for subject in ("math", "english")
            }
            add_event(db, s.id, "exam_taken", dt(exam.exam_date, time(9, 0)),
                      ref_table="exam", ref_id=exam.id,
                      payload={"exam": exam.name,
                               "scores": scores})

    # --- home visits + notes -------------------------------------------------
    visits = [
        (hao.id, zhao.id, datetime(2026, 3, 20, 19, 0),
         "频繁迟到",
         "父母上早班，商定由爷爷负责早餐和晨间作息。",
         True, "四月中旬再次检查出勤情况"),
        (lin.id, chen.id, datetime(2026, 5, 10, 19, 30),
         "数学提升计划",
         "与家长沟通分数专项练习计划：每周二、周四各练习20分钟。",
         False, None),
        (guo.id, zhao.id, datetime(2026, 6, 5, 18, 30),
         "期末走访",
         "家庭支持到位，学生自述备考状态良好。",
         False, None),
    ]
    for student_id, teacher_id, when, purpose, summary, follow_up, note in visits:
        add_event(db, student_id, "home_visited", when, actor_teacher_id=teacher_id,
                  payload={"purpose": purpose, "summary": summary,
                           "follow_up_needed": follow_up, "follow_up_note": note})

    add_event(db, lin.id, "note_added", datetime(2026, 4, 20, 15, 0),
              actor_teacher_id=chen.id,
              payload={"note": "对多步骤分数应用题掌握不牢，建议用画图法辅助理解。",
                       "category": "study_habits"})
    add_event(db, hao.id, "note_added", datetime(2026, 3, 22, 15, 0),
              actor_teacher_id=zhao.id,
              payload={"note": "家庭约定后，出勤情况明显改善。",
                       "category": "behavior"})


def run() -> None:
    # True schema reset through Alembic: downgrade to base removes all tables
    # INCLUDING the alembic_version stamp, so re-seeding an already-stamped DB
    # actually rebuilds instead of upgrading to a no-op.
    command.downgrade(_alembic_config(), "base")
    # Migrations — not create_all — own the schema now.
    command.upgrade(_alembic_config(), "head")
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        print("Seed complete:")
        print(f"  users: {db.query(User).count()}")
        print(f"  students: {db.query(Student).count()}")
        print(f"  exam_results: {db.query(ExamResult).count()}")
        print(f"  timeline_events: {db.query(StudentEvent).count()}")
        print("  demo login: 13800000001 / 123456")
        print("  admin login: 13800000000 / admin123  → hidden /admin dashboard")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
