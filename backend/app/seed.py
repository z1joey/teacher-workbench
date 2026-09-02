"""Create tables and load demo data. Run from backend/: python -m app.seed

Demo content is Chinese-only: names, visits and notes are stored as plain text.

Note (2026-09): KnowledgePoint / Question / QuestionResponse / StudentWeakness
tables have been REMOVED. Exam scores are generated directly at the subject
level (ExamResult row per student per exam subject).
"""
import random
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .events import add_event
from .models import (
    Class,
    Enrollment,
    Exam,
    ExamResult,
    ExamSubject,
    Student,
    StudentEvent,
    Teacher,
)
from .security import hash_password

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
    admin = Teacher(name="开发者", email="admin@school.dev", phone="13800000000",
                    password_hash=hash_password("admin123"), subject=None, is_admin=True)
    chen = Teacher(name="陈老师", email="chen@school.edu", phone="13800000001",
                   password_hash=hash_password("123456"), subject="math")
    zhao = Teacher(name="赵老师", email="zhao@school.edu", phone="13800000002",
                   password_hash=hash_password("123456"), subject="english")
    db.add_all([admin, chen, zhao])
    db.flush()

    c71 = Class(name="七年级1班", grade_level=7,
                academic_year=ACADEMIC_YEAR, homeroom_teacher_id=chen.id)
    c72 = Class(name="七年级2班", grade_level=7,
                academic_year=ACADEMIC_YEAR, homeroom_teacher_id=zhao.id)
    db.add_all([c71, c72])
    db.flush()

    midterm = Exam(name="期中考试", exam_date=date(2026, 4, 15))
    final = Exam(name="期末考试", exam_date=date(2026, 6, 25))
    db.add_all([midterm, final])
    db.flush()
    exams_by_key = {"midterm": midterm, "final": final}

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
    # Midterm / Final trend: final is generally 3 pts higher, + noise.
    exam_trend = {"midterm": 0.0, "final": 3.0}

    result_by_key: dict[tuple[int, str, str], ExamResult] = {}

    for exam_key, exam in exams_by_key.items():
        for subject in ("math", "english"):
            es = exam_subject_by_key[(exam_key, subject)]
            entering_teacher = chen if subject == "math" else zhao
            for s in students:
                base = ability[s.id][subject] + exam_trend[exam_key] + random.gauss(0, 3.0)
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

    # story: 王浩 moves 七年级2班 -> 七年级1班 on 2026-03-01 (before both exams)
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
    for exam_key, exam in exams_by_key.items():
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
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        print("Seed complete:")
        print(f"  students: {db.query(Student).count()}")
        print(f"  exam_results: {db.query(ExamResult).count()}")
        print(f"  timeline_events: {db.query(StudentEvent).count()}")
        print("  (question_responses & weakness tables removed)")
        print("  demo login: 13800000001 / 123456")
        print("  admin login: 13800000000 / admin123  → hidden /admin dashboard")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
