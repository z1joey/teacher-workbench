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
from .eventing import sync_all_birthday_events
from .unassigned import ensure_unassigned_class
from .workspace import ensure_workspace_id, tag_student_workspace
from .eventing import create_event
from .models import Class, ClassSeating, Enrollment, Event, Person, Tag, student_guardians
from .payloads import validate_person_payload
from .routers.students import _find_or_create_guardian, _guardians_of
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


# Personal events for list-card previews (评语 / 家访 only — birthdays come
# from sync_all_birthday_events). Dated after birthday sync so cards are not
# all 🎂 when a student has no other personal follow-up.
_CARD_COMMENT_NOTES = [
    "乐于助人，值日认真负责，是班级的稳定力量。",
    "思维活跃，课堂提问有深度，期待更多分享。",
    "做事踏实，作业完成质量稳步提升。",
    "与同学相处融洽，团队项目里配合默契。",
]
_CARD_VISIT_SUMMARIES = [
    ("学业沟通", "与家长沟通近期课堂表现，家庭配合良好。"),
    ("行为习惯", "反馈作业完成情况，约定每日自查清单。"),
    ("作业习惯", "沟通晚间作息，家长表示会控制电子产品使用。"),
    ("期末回访", "了解假期安排，鼓励学生保持阅读习惯。"),
]


def _apply_completed_home_visit_tags(db: Session) -> None:
    """Mirror mark-done API: completed visits earn the 已家访 student tag."""
    from .models import person_tags

    tag = db.query(Tag).filter(Tag.name == "已家访").first()
    if tag is None:
        tag = Tag(name="已家访", color="#2f7d4f")
        db.add(tag)
        db.flush()
    for ev in db.query(Event).filter(Event.type == "home_visited").all():
        if not (ev.payload or {}).get("done"):
            continue
        for person in ev.attendees:
            if person.role != "student":
                continue
            exists = (
                db.query(person_tags)
                .filter(
                    person_tags.c.person_id == person.id,
                    person_tags.c.tag_id == tag.id,
                )
                .first()
            )
            if exists is None:
                db.execute(
                    person_tags.insert().values(person_id=person.id, tag_id=tag.id)
                )


def _seed_list_card_events(db: Session, students: list[Person], teacher: Person) -> None:
    """Give students without a story visit a recent 评语 or 家访 for list cards."""
    story_names = {
        "林晓雨", "王浩", "徐曼怡", "郭浩然", "邓晓彤", "周子涵", "韩如冰",
        "冯俊豪", "宋雅轩", "乔安琪", "唐美琳", "罗蔚一", "高子辰",
    }
    for i, student in enumerate(students):
        if student.name in story_names:
            continue
        when = dt(date(2026, 10, 1 + (i % 20)), time(9 + (i % 6), 15 + (i % 45)))
        if i % 2 == 0:
            notes = _CARD_COMMENT_NOTES[i % len(_CARD_COMMENT_NOTES)]
            create_event(
                db,
                event_type="comment",
                title=notes[:100],
                start_time=when,
                payload={
                    "notes": notes,
                    "about": {"id": str(student.id), "name": student.name},
                    "mentioned": [],
                },
                attendee_ids=[student.id, teacher.id],
            )
        else:
            purpose, summary = _CARD_VISIT_SUMMARIES[i % len(_CARD_VISIT_SUMMARIES)]
            guardians = _guardians_of(db, student.id)
            # Leave a couple of routine visits open so the visits page shows
            # follow-up work beyond the main story arcs.
            done = student.name not in {"吴一凡", "潘书涵"}
            create_event(
                db,
                event_type="home_visited",
                title=summary[:100],
                start_time=when,
                payload={
                    "summary": summary,
                    "purpose": purpose,
                    "done": done,
                    "guardian": guardians[0][0].name if guardians else None,
                },
                attendee_ids=[student.id, teacher.id],
            )


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
    wid = ensure_workspace_id(teacher)
    c71 = Class(name="七年级1班", academic_year=ACADEMIC_YEAR, teacher_id=teacher.id)
    c72 = Class(name="七年级2班", academic_year=ACADEMIC_YEAR, teacher_id=teacher.id)
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
            tag_student_workspace(s, teacher)
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
                     "subject_colors": dict(SUBJECT_COLORS),
                     "workspace_id": wid},
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
                                 "max_score": SUBJECT_FULL_SCORES[subject],
                                 "workspace_id": wid}
                if (s.id, exam_key, subject) in ABSENCES:
                    payload["absent"] = True
                else:
                    payload["score"] = score
                create_event(db, event_type="score",
                             title=f"{exam.title}·{subject}",
                             start_time=dt(exam.start_time.date(), EXAM_HOUR),
                             payload=payload, attendee_ids=[s.id, teacher.id])
    db.flush()

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

    # --- 座位表演示：两个班各一张常驻布局，留几个空座更接近真实教室 ---------
    # seats 为 {行优先座位序号: 学生}；林晓雨(需关注)固定前排，王浩转班后坐末排
    seating_plan = {
        c71.id: (4, 4, {  # 4 排 4 列，末排只坐转班来的王浩
            "0": "林晓雨", "1": "陈佳怡", "2": "周子涵", "3": "吴一凡",
            "4": "宋雅轩", "5": "徐曼怡", "6": "高子辰", "7": "韩如冰",
            "8": "乔安琪", "9": "冯俊豪", "10": "唐美琳", "11": "罗蔚一",
            "12": "王浩",
        }),
        c72.id: (4, 3, {  # 4 排 3 列，末排一个空座
            "0": "郭浩然", "1": "李思彤", "2": "张悦",
            "3": "刘宇宸", "4": "何佳欣", "5": "崔明轩",
            "6": "潘书涵", "7": "袁志远", "8": "邓晓彤",
            "9": "任凯文", "10": "沈洛一",
        }),
    }
    for class_id, (rows, cols, layout) in seating_plan.items():
        db.add(ClassSeating(
            class_id=class_id,
            rows=rows,
            cols=cols,
            seats={pos: str(by_name[name].id) for pos, name in layout.items()},
        ))
    db.flush()

    # 开学排座同样留痕：每位就座学生一条换座位事件（王浩的是转班后的新安排）
    for class_id, (rows, cols, layout) in seating_plan.items():
        for pos, name in layout.items():
            i = int(pos)
            student = by_name[name]
            day = (
                date(2026, 3, 2)
                if (name == "王浩" and class_id == c71.id)
                else date(2025, 9, 2)
            )
            create_event(db, event_type="seat_changed", title="换座位",
                         start_time=dt(day, time(8, 40)),
                         payload={"to": f"第{i // cols + 1}排第{i % cols + 1}列"},
                         attendee_ids=[student.id])

    # --- home visits + 评语 -------------------------------------------------
    # Visits involve 陈老师 (the visiting teacher), the student and the
    # guardian of record (snapshotted from the linked guardian Person); notes
    # involve her and the student. Home-visit purpose folds into the summary
    # (HomeVisitPayload has summary/purpose/guardian only). Several visits stay
    # undone so the 待跟进 queue has realistic follow-up work.
    visits = [
        (hao, datetime(2026, 3, 20, 19, 0), "行为习惯", True,
         "频繁迟到：父母上早班，商定由爷爷负责早餐和晨间作息。"),
        (lin, datetime(2026, 5, 10, 19, 30), "学业沟通", True,
         "数学提升计划：与家长沟通分数专项练习计划，每周二、周四各练习20分钟。"),
        (xu := by_name["徐曼怡"], datetime(2026, 4, 11, 18, 30), "作业习惯", True,
         "父母反映回家作业拖拉，约定使用番茄钟计划表，每周末电话跟进一次。"),
        (guo, datetime(2026, 6, 5, 18, 30), "期末走访", True,
         "期末走访：家庭支持到位，学生自述备考状态良好。"),
        (deng := by_name["邓晓彤"], datetime(2026, 7, 2, 19, 0), "期末回访", False,
         "约期末后回访，了解转班前后学习状态的变化，准备暑期建议。"),
        (by_name["张悦"], datetime(2026, 8, 28, 18, 30), "开学适应", False,
         "新学期第一周家访：了解假期作业完成情况与作息调整，协助制定学习计划。"),
        (by_name["任凯文"], datetime(2026, 9, 8, 19, 0), "作业质量", False,
         "近期作业潦草、订正不及时，约家长面谈辅导方案与家校配合方式。"),
        (by_name["袁志远"], datetime(2026, 9, 12, 18, 0), "学业预警", False,
         "数学小测连续偏低，计划与家长沟通课后辅导安排，观察两周后回访。"),
    ]
    for student, when, purpose, done, summary in visits:
        guardians = _guardians_of(db, student.id)
        create_event(db, event_type="home_visited", title=summary[:100], start_time=when,
                     payload={"summary": summary,
                              "purpose": purpose,
                              "done": done,
                              "guardian": guardians[0][0].name if guardians else None},
                     attendee_ids=[student.id, teacher.id])

    song = by_name["宋雅轩"]
    qiao = by_name["乔安琪"]
    tang = by_name["唐美琳"]
    zhou = by_name["周子涵"]
    han = by_name["韩如冰"]
    feng = by_name["冯俊豪"]
    luo = by_name["罗蔚一"]
    gaozc = by_name["高子辰"]

    def comment(about, when, notes, mentioned=(), title=None):
        create_event(db, event_type="comment", title=title or notes[:100], start_time=when,
                     payload={"notes": notes,
                              "about": {"id": str(about.id), "name": about.name},
                              "mentioned": [{"id": str(m.id), "name": m.name}
                                            for m in mentioned]},
                     attendee_ids=[about.id, *[m.id for m in mentioned], teacher.id])

    comment(lin, datetime(2026, 4, 24, 16, 0),
            "近期数学课堂发言积极，画图法用得越来越好，继续保持这股劲头。")
    comment(song, datetime(2026, 4, 29, 17, 0),
            "运动会报名组织有序，平时也乐于帮同学讲题，很有小老师的样子。",
            mentioned=[tang, qiao])
    comment(hao, datetime(2026, 3, 27, 16, 30),
            "转班后适应得不错，数学方程部分仍需巩固，已安排每周一次辅导。")
    comment(lin, datetime(2026, 4, 20, 15, 0),
            "对多步骤分数应用题掌握不牢，建议用画图法辅助理解。")
    comment(hao, datetime(2026, 3, 22, 15, 0),
            "家庭约定后，出勤情况明显改善。")
    comment(hao, datetime(2026, 3, 4, 16, 0),
            "转班第一天，聊聊新班级的节奏，安排同桌互相认识。")
    comment(zhou, datetime(2026, 3, 12, 16, 20),
            "课间与同学起争执，谈心后互相道歉，约定值日分工轮流来。")
    comment(lin, datetime(2026, 4, 8, 16, 30),
            "数学辅导：分数应用题画图法专项练习。")
    comment(lin, datetime(2026, 4, 15, 16, 30),
            "数学辅导：画图法巩固，正确率明显提升。")
    comment(hao, datetime(2026, 3, 11, 16, 30),
            "数学辅导：一元一次方程去括号易错点。")
    comment(han, datetime(2026, 5, 6, 19, 30),
            "反映近期上课走神，家长表示会调整晚间作息，控制电子产品使用。")
    comment(feng, datetime(2026, 6, 20, 18, 0),
            "电话表扬期末进步明显，家长很受鼓舞，表示暑假坚持阅读打卡。")
    comment(song, datetime(2026, 4, 28, 10, 0),
            "宋雅轩以3分12秒夺得第一名，为班级积8分。",
            title="校运会女子800米决赛")
    comment(luo, datetime(2026, 4, 28, 15, 0),
            "罗蔚一以4米35获得第三名。",
            title="校运会男子跳远")
    comment(qiao, datetime(2026, 5, 16, 14, 0),
            "三人组队参赛，乔安琪获最佳朗诵奖。",
            mentioned=[tang, han], title="语文课文朗诵比赛")
    comment(gaozc, datetime(2026, 5, 22, 15, 30),
            "高子辰获二等奖，王浩坚持完成全部赛题。",
            mentioned=[hao], title="数学趣味竞赛")

    # --- 学生总结（AI 生成的阶段性总结，只进教师自己的动态）-------------------
    def summary(about, when, content, params):
        create_event(db, event_type="summary", title="学生总结", start_time=when,
                     payload={"summary": content, "params": params,
                              "about": {"id": str(about.id), "name": about.name}},
                     attendee_ids=[about.id, teacher.id])

    summary(lin, datetime(2026, 1, 23, 17, 0),
            "林晓雨本学期整体表现稳定，语文阅读理解进步明显，数学应用题是主要短板。"
            "10月起实施数学提升计划，每周两次画图法专项练习，期末数学较期中提升明显。"
            "课堂上乐于发言，与同学相处融洽。下学期建议继续巩固计算准确率，养成错题整理习惯。",
            {"length": "standard", "style": "formal",
             "date_from": "2025-09-01", "date_to": "2026-01-22"})
    summary(lin, datetime(2026, 6, 26, 16, 0),
            "林晓雨本学年学业持续进步，数学通过一学期的专项辅导，画图法应用明显熟练，"
            "期末各科成绩较秋季学期均有提升。英语口语表达更自信，班级活动中积极参与。"
            "家庭配合度高，母亲能按约定跟进每日作业自查。升入八年级前建议保持当前节奏，重点补强物理入门。",
            {"length": "detailed", "style": "formal",
             "date_from": "2025-09-01", "date_to": "2026-06-25"})
    summary(hao, datetime(2026, 3, 20, 17, 30),
            "王浩这学期经历转班适应期，起初因频繁迟到数学有所下滑，但3月起出勤明显改善，"
            "课堂参与度提高。他性格开朗，与同学关系好，数学趣味竞赛坚持完成全部赛题值得肯定。"
            "希望家长继续督促早睡早起，稳定出勤后成绩会稳步回升。",
            {"length": "standard", "style": "warm",
             "date_from": "2026-01-22", "date_to": "2026-03-20"})
    summary(guo, datetime(2026, 6, 26, 17, 0),
            "郭浩然是班级的理科小明星，数学趣味竞赛获二等奖，物理化学稳居班级前列，语文成绩稳中有升。"
            "若能在英语听力上再下功夫，总分还有上升空间。继续保持这份钻研劲头，"
            "八年级期待你带动更多同学一起进步！",
            {"length": "standard", "style": "motivational",
             "date_from": "2026-03-01", "date_to": "2026-06-25"})
    summary(xu, datetime(2026, 5, 12, 17, 0),
            "徐曼怡近来作业完成节奏偏慢，但课堂听讲专注、态度端正。已与家长建立每周电话跟进机制，"
            "使用番茄钟计划表后回家效率有所提高。建议继续强化时间管理能力，英语单词背诵需每日坚持。",
            {"length": "standard", "style": "warm",
             "date_from": "2026-01-22", "date_to": "2026-05-10"})
    summary(deng, datetime(2026, 7, 5, 16, 30),
            "邓晓彤转班后整体适应良好，与原班级相比课堂发言更积极。期末回访待完成，"
            "需进一步了解暑期学习安排与作息调整情况。数学基础扎实，语文阅读可再加强。",
            {"length": "brief", "style": "formal",
             "date_from": "2026-03-01", "date_to": "2026-07-02"})
    summary(song, datetime(2026, 5, 1, 17, 0),
            "宋雅轩综合素质突出，校运会女子800米夺冠，班级活动组织能力强，"
            "平时乐于帮助同学解题。学业方面各科均衡，语文朗诵比赛获最佳朗诵奖。"
            "是学校活动的骨干力量，建议在学习上进一步挑战更高难度的数学题目。",
            {"length": "detailed", "style": "motivational",
             "date_from": "2025-09-01", "date_to": "2026-04-30"})

    sync_all_birthday_events(db)
    _seed_list_card_events(db, students, teacher)
    _apply_completed_home_visit_tags(db)

    # --- 毕业归档：上一届班级整体毕业（数据保留，默认列表隐藏）--------------
    # 学生：graduated_at + is_active=False + 「已毕业」标签，学籍关闭于毕业日；
    # 班级：archived=True。全部在个人中心「毕业归档」卡片中可见。
    GRAD_YEAR = "2024/2025"
    GRAD_DATE = date(2025, 7, 4)
    c61 = Class(name="六1班", academic_year=GRAD_YEAR, teacher_id=teacher.id, archived=True)
    db.add(c61)
    db.flush()
    grad_tag = Tag(name="已毕业", color="#b7791f")
    db.add(grad_tag)
    db.flush()

    GRAD_NAMES = [
        ("赵一诺", "F"), ("钱思远", "M"), ("孙悦宁", "F"),
        ("黄嘉树", "M"), ("范雨桐", "F"), ("魏子墨", "M"),
    ]
    for i, (name, gender) in enumerate(GRAD_NAMES):
        payload = validate_person_payload("student", {
            "admission_no": f"S2024{301 + i:03d}",
            "gender": gender,
            "birth_date": date(2011, random.randint(1, 12), random.randint(1, 28)).isoformat(),
            "address": f"文化路{200 + i}号",
            "is_active": False,
            "graduated_at": GRAD_DATE.isoformat(),
        })
        s = Person(name=name, password_hash=hash_password(uuid.uuid4().hex),
                   payload=payload)
        db.add(s)
        db.flush()
        tag_student_workspace(s, teacher)
        guardian = _find_or_create_guardian(
            db, f"{name[0]}女士", f"137{random.randint(10_000_000, 99_999_999)}"
        )
        db.execute(student_guardians.insert().values(
            student_id=s.id, guardian_id=guardian.id
        ))
        db.add(Enrollment(
            person_id=s.id, class_id=c61.id,
            valid_from=date(2024, 9, 1), valid_to=GRAD_DATE, reason="admitted",
        ))
        create_event(db, event_type="enrolled", title="入学",
                     start_time=dt(date(2024, 9, 1), time(8, 0)),
                     payload={"class_name": c61.name}, attendee_ids=[s.id])
        create_event(db, event_type="graduated", title="毕业",
                     start_time=dt(GRAD_DATE, time(10, 0)),
                     payload={"class_name": c61.name}, attendee_ids=[s.id])
        grad_tag.people.append(s)
    db.flush()
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
        archived_classes = db.query(Class).filter(Class.archived.is_(True)).count()
        print(f"  archived classes: {archived_classes}")
        print(f"  tags: {db.query(Tag).count()}")
        print(f"  enrollments: {db.query(Enrollment).count()}")
        print("  demo login: chen@school.edu / 123456")
        print("  admin login: admin@school.dev / admin123  → hidden /admin dashboard")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
