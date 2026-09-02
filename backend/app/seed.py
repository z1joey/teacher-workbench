"""Create tables and load demo data. Run from backend/: python -m app.seed

Demo content is Chinese-only: names, knowledge points, visits and notes are
stored as plain text.
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
    KnowledgePoint,
    Question,
    QuestionResponse,
    Student,
    StudentEvent,
    StudentWeakness,
    Teacher,
)
from .security import hash_password

random.seed(2026)

ACADEMIC_YEAR = "2025/2026"
ENROLL_DATE = date(2025, 9, 1)

SUBJECT_FULL_SCORE = 100.0
PASS_RATIO = 0.6

# (code, name)
MATH_KPS = [
    ("MATH.G7.INTEGERS", "整数运算"),
    ("MATH.G7.FRACTION.ADD", "分数加减法"),
    ("MATH.G7.FRACTION.MULT", "分数乘除法"),
    ("MATH.G7.EQUATION.LINEAR", "一元一次方程"),
    ("MATH.G7.GEOMETRY.ANGLE", "角与平行线"),
]
ENG_KPS = [
    ("ENG.G7.READING.DETAIL", "阅读理解·细节题"),
    ("ENG.G7.READING.INFER", "阅读理解·推断题"),
    ("ENG.G7.GRAMMAR.PAST", "动词过去式"),
    ("ENG.G7.VOCAB", "词汇运用"),
]

# (question_no, knowledge_point code, max_score, question_type)
MATH_QUESTIONS = [
    ("1", "MATH.G7.INTEGERS", 10, "calculation"),
    ("2", "MATH.G7.INTEGERS", 10, "calculation"),
    ("3", "MATH.G7.FRACTION.ADD", 10, "calculation"),
    ("4", "MATH.G7.FRACTION.ADD", 10, "word_problem"),
    ("5", "MATH.G7.FRACTION.MULT", 10, "calculation"),
    ("6", "MATH.G7.FRACTION.MULT", 10, "word_problem"),
    ("7", "MATH.G7.EQUATION.LINEAR", 10, "calculation"),
    ("8", "MATH.G7.EQUATION.LINEAR", 10, "word_problem"),
    ("9", "MATH.G7.GEOMETRY.ANGLE", 10, "geometry"),
    ("10", "MATH.G7.GEOMETRY.ANGLE", 10, "geometry"),
]
ENG_QUESTIONS = [
    ("1", "ENG.G7.READING.DETAIL", 20, "choice"),
    ("2", "ENG.G7.READING.DETAIL", 20, "choice"),
    ("3", "ENG.G7.READING.INFER", 20, "choice"),
    ("4", "ENG.G7.GRAMMAR.PAST", 20, "fill-in"),
    ("5", "ENG.G7.VOCAB", 20, "choice"),
]

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

    kp_by_code: dict[str, KnowledgePoint] = {}
    for code, name in MATH_KPS:
        kp_by_code[code] = KnowledgePoint(subject="math", code=code, name=name)
    for code, name in ENG_KPS:
        kp_by_code[code] = KnowledgePoint(subject="english", code=code, name=name)
    db.add_all(kp_by_code.values())
    db.flush()
    kp_name_by_id = {kp.id: kp.name for kp in kp_by_code.values()}

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

    questions_by_es: dict[int, list[Question]] = {}
    question_by_key: dict[tuple[int, str], Question] = {}
    pending_kp_codes: list[tuple[Question, str]] = []  # (question, kp code) — ids assign at flush
    for (exam_key, subject), es in exam_subject_by_key.items():
        blueprint = MATH_QUESTIONS if subject == "math" else ENG_QUESTIONS
        created = []
        for no, code, max_score, qtype in blueprint:
            q = Question(exam_subject_id=es.id, question_no=no,
                         knowledge_point_id=kp_by_code[code].id,
                         question_type=qtype, max_score=max_score)
            db.add(q)
            created.append(q)
            question_by_key[(es.id, no)] = q
            pending_kp_codes.append((q, code))
        created.sort(key=lambda q: int(q.question_no))
        questions_by_es[es.id] = created
    db.flush()
    kp_code_by_qid = {q.id: code for q, code in pending_kp_codes}

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

    # --- ability model ----------------------------------------------------
    ability = {
        s.id: {"math": random.gauss(72, 12), "english": random.gauss(70, 13)}
        for s in students
    }
    kp_affinity = {
        (s.id, code): random.uniform(-10, 6)
        for s in students
        for code in kp_by_code
    }
    # story overrides so the demo shows clear, explainable patterns
    ability[lin.id]["math"] = 58.0
    kp_affinity[(lin.id, "MATH.G7.FRACTION.ADD")] = -22.0
    kp_affinity[(lin.id, "MATH.G7.FRACTION.MULT")] = -14.0
    kp_affinity[(hao.id, "MATH.G7.EQUATION.LINEAR")] = -18.0

    # --- responses + results ----------------------------------------------
    response_by_key: dict[tuple[int, int], QuestionResponse] = {}
    result_by_key: dict[tuple[int, str, str], ExamResult] = {}

    for exam_key, exam in exams_by_key.items():
        for subject in ("math", "english"):
            es = exam_subject_by_key[(exam_key, subject)]
            entering_teacher = chen if subject == "math" else zhao
            for s in students:
                total = 0.0
                for q in questions_by_es[es.id]:
                    base = clamp(
                        ability[s.id][subject] + kp_affinity.get((s.id, kp_code_by_qid[q.id]), 0.0),
                        5.0, 100.0,
                    )
                    ratio = clamp(base / 100.0 + random.gauss(0, 0.10), 0.0, 1.0)
                    earned = round(q.max_score * ratio, 1)
                    qr = QuestionResponse(
                        student_id=s.id, question_id=q.id, earned=earned,
                        is_correct=earned >= PASS_RATIO * q.max_score,
                    )
                    db.add(qr)
                    response_by_key[(s.id, q.id)] = qr
                    total += earned
                result = ExamResult(
                    student_id=s.id, exam_subject_id=es.id,
                    score=round(total, 1), status="entered",
                    entered_by=entering_teacher.id,
                )
                db.add(result)
                db.flush()
                result_by_key[(s.id, exam_key, subject)] = result

    # story: 陈老师 corrects an addition error on 林晓雨's midterm math Q7
    lin_math_midterm = result_by_key[(lin.id, "midterm", "math")]
    q7 = question_by_key[(exam_subject_by_key[("midterm", "math")].id, "7")]
    qr7 = response_by_key[(lin.id, q7.id)]
    old_score = lin_math_midterm.score
    qr7.earned = round(min(qr7.earned + 5.0, q7.max_score), 1)
    qr7.is_correct = qr7.earned >= PASS_RATIO * q7.max_score
    lin_math_midterm.score = round(lin_math_midterm.score + 5.0, 1)
    add_event(db, lin.id, "result_changed", dt(date(2026, 4, 16), time(16, 30)),
              actor_teacher_id=chen.id, ref_table="exam_result",
              ref_id=lin_math_midterm.id,
              payload={"exam": midterm.name,
                       "subject": "math", "old": old_score, "new": lin_math_midterm.score,
                       "reason": "第7题加法错误更正"})

    # story: 王浩 moves 七年级2班 -> 七年级1班 on 2026-03-01 (before both exams,
    # so his averages attribute to 7-1 even though he started in 7-2)
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

    # --- timeline: exam events ---------------------------------------------
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

    # --- weaknesses rollup ---------------------------------------------------
    for s in students:
        agg: dict[int, dict] = {}
        for exam_key, exam in exams_by_key.items():
            for subject in ("math", "english"):
                es = exam_subject_by_key[(exam_key, subject)]
                for q in questions_by_es[es.id]:
                    qr = response_by_key[(s.id, q.id)]
                    rec = agg.setdefault(q.knowledge_point_id, {
                        "attempts": 0, "fails": 0, "first": None,
                        "last": None, "final_fails": 0,
                    })
                    rec["attempts"] += 1
                    if not qr.is_correct:
                        rec["fails"] += 1
                        rec["first"] = rec["first"] or exam.exam_date
                        rec["last"] = exam.exam_date
                        if exam_key == "final":
                            rec["final_fails"] += 1

        flagged_by_date: dict[date, list[dict]] = {}
        for kp_id, rec in agg.items():
            if rec["fails"] >= 2:
                status = "resolved" if rec["final_fails"] == 0 else "open"
                db.add(StudentWeakness(
                    student_id=s.id, knowledge_point_id=kp_id,
                    evidence_count=rec["fails"], attempts=rec["attempts"],
                    severity=rec["fails"] / rec["attempts"], status=status,
                    first_seen=rec["first"], last_seen=rec["last"],
                    last_exam_id=final.id,
                ))
                flagged_by_date.setdefault(rec["first"], []).append(kp_name_by_id[kp_id])
        for first_date, kp_names in flagged_by_date.items():
            add_event(db, s.id, "weakness_flagged", dt(first_date, time(17, 0)),
                      payload={"points": kp_names})

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
        print(f"  question_responses: {db.query(QuestionResponse).count()}")
        print(f"  weaknesses: {db.query(StudentWeakness).count()}")
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
