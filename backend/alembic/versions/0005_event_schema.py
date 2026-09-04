"""event schema: migrate legacy column data into person + event.

One-way rebuild. The table-name collisions (class/tag/enrollment/auth_session
exist in both schemas) force this order: READ every legacy row into Python,
DROP all legacy tables, create the new schema straight from app.models
metadata (model parity for free — UUID PKs, expression/partial indexes, and
the PG-only GIN payloads appear per dialect), then INSERT transformed rows
with fresh uuid4 PKs, keeping a remap dict per legacy id. No ORM, no server
round-trips per row: one SELECT per legacy table, one executemany per new
table.

downgrade is NOT implemented — payload → columns is lossy (free-form event
payloads, throwaway student password hashes, dropped actor_teacher_id/ref_*
columns); restore from a pre-migration backup instead. SQLite dev databases
are not migrated — delete the file and re-seed (python -m app.seed); the
migration target is the docker PostgreSQL database.

Transformations (controller-resolved conventions):
- user (+teacher_profile) / student → person: role + profile live in
  person.payload (registry shapes, app.payloads), phone/email/password_hash
  as-is for accounts; students get phone NULL and a throwaway uuid4 hex
  password; student.status → payload.is_active (False unless "active").
- class/enrollment → same tables, new UUID ids, person/class FKs remapped.
- exam + exam_subject + exam_result → one Event(type="exam") per sitting
  (title=exam.name, exam day 09:00, payload.full_scores={subject: full_score},
  attendees=the students holding results) plus one Event(type="score") per
  exam_result (title="{exam}·{subject}", payload {subject, max_score, score,
  absent}; absent rows carry {"absent": true} and no score key).
- student_event → Event(type=event_type) 1:1: title/description from the
  legacy payload, payload passed through free-form; recurrence /
  actor_teacher_id / ref_* are dropped. Birthday rows migrate as the single
  past occurrence (future birthdays are projected from payload birth_date).
- tag → tag; student_tag → person_tags; auth_session keeps its token with
  person_id remapped (rows for unknown users are dropped).
- created_at/updated_at are preserved where the legacy table had them and
  set to the migration time otherwise (Event.created_at breaks score-title
  ties the way the old autoincrement id did — insertion order).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04
"""
import json
import uuid
from datetime import date, datetime, time

import sqlalchemy as sa
from alembic import op

import app.models  # noqa: F401  (registers the new tables on Base.metadata)
from app.database import Base
from app.models._common import JSONType, utcnow

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# legacy tables, children before parents (legacy FKs noted)
_LEGACY_TABLES = [
    "exam_result",      # → student, exam_subject
    "exam_subject",     # → exam
    "exam",             # —
    "student_tag",      # → student, tag
    "tag",              # —
    "enrollment",       # → student, class
    "class",            # → user (homeroom_teacher_id)
    "student_event",    # → student, user (actor_teacher_id)
    "student",          # —
    "auth_session",     # → user
    "teacher_profile",  # → user
    "user",             # —
]

EXAM_HOUR = time(9, 0)  # sittings and their score rows are dated the exam day 09:00


def _as_date(value):
    """Legacy DATE column → datetime.date (SQLite raw selects return str)."""
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _as_datetime(value):
    """Legacy DATETIME column → datetime (SQLite raw selects return str)."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.fromisoformat(str(value))


def _as_dict(value):
    """Legacy JSON payload → dict (TEXT on SQLite, parsed on PostgreSQL)."""
    if value is None:
        return {}
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return dict(value)


# sa.table/sa.column: unbound DML constructs — types drive the bind processors
# (UUID hex packing, JSON serialization, date formatting) on both dialects.
def _t(name, *cols):
    return sa.table(name, *cols)


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Guard: without the legacy "user" table there is nothing to migrate.
    # "person" present → this database is already migrated: no-op. Neither
    # table → fresh database: just build the new schema, no data.
    if not inspector.has_table("user"):
        if not inspector.has_table("person"):
            Base.metadata.create_all(conn)
        return

    # 1. READ every legacy row into Python --------------------------------
    def _rows(sql):
        return [r._mapping for r in conn.execute(sa.text(sql))]

    users = {r["id"]: r for r in _rows('SELECT * FROM "user"')}
    profiles = {r["user_id"]: r["subject"]
                for r in _rows("SELECT user_id, subject FROM teacher_profile")}
    students = {r["id"]: r for r in _rows("SELECT * FROM student")}
    classes = {r["id"]: r for r in _rows("SELECT * FROM class")}
    enrollments = {r["id"]: r for r in _rows("SELECT * FROM enrollment")}
    exams = {r["id"]: r for r in _rows("SELECT * FROM exam")}
    subjects_by_exam: dict[int, list] = {}
    for r in _rows("SELECT * FROM exam_subject"):
        subjects_by_exam.setdefault(r["exam_id"], []).append(r)
    subject_by_id = {s["id"]: s
                     for rows in subjects_by_exam.values() for s in rows}
    results_by_exam: dict[int, list] = {}
    for r in _rows("SELECT * FROM exam_result"):
        results_by_exam.setdefault(subject_by_id[r["exam_subject_id"]]["exam_id"], []).append(r)
    student_events = _rows("SELECT * FROM student_event")
    tags = {r["id"]: r for r in _rows("SELECT * FROM tag")}
    student_tags = _rows("SELECT * FROM student_tag")
    auth_sessions = _rows("SELECT * FROM auth_session")

    # 2. DROP all legacy tables (names collide with the new schema) --------
    for table in _LEGACY_TABLES:
        op.drop_table(table)

    # 3. CREATE the new schema from the models metadata --------------------
    Base.metadata.create_all(conn)

    # 4. TRANSFORM + INSERT ------------------------------------------------
    now = utcnow()
    person_rows, tag_rows, class_rows, enrollment_rows = [], [], [], []
    event_rows, person_event_rows, person_tag_rows, session_rows = [], [], [], []

    user_person: dict[int, uuid.UUID] = {}
    student_person: dict[int, uuid.UUID] = {}
    class_remap: dict[int, uuid.UUID] = {}
    tag_remap: dict[int, uuid.UUID] = {}

    # accounts (user ⨝ teacher_profile) → person
    for uid, u in users.items():
        user_person[uid] = uuid.uuid4()
        payload = {"role": u["role"], "name": u["name"],
                   "is_active": bool(u["is_active"])}
        subject = profiles.get(uid)
        if u["role"] == "teacher" and subject is not None:
            payload["subject"] = subject
        created = _as_datetime(u["created_at"]) or now
        person_rows.append({
            "id": user_person[uid], "phone": u["phone"], "email": u["email"],
            "password_hash": u["password_hash"], "payload": payload,
            "created_at": created, "updated_at": created,
        })

    # students → person (columns → registry payload 1:1, NULLs omitted)
    for sid, st in students.items():
        student_person[sid] = uuid.uuid4()
        birth = _as_date(st["birth_date"])
        payload = {
            "role": "student",
            "name": st["name"],
            "admission_no": st["admission_no"],
            "gender": st["gender"],
            "birth_date": birth.isoformat() if birth is not None else None,
            "guardian_name": st["guardian_name"],
            "guardian_phone": st["guardian_phone"],
            "address": st["address"],
            "is_active": st["status"] == "active",
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        created = _as_datetime(st["created_at"]) or now
        person_rows.append({
            "id": student_person[sid], "phone": None, "email": None,
            "password_hash": uuid.uuid4().hex,  # students don't log in
            "payload": payload,
            "created_at": created,
            "updated_at": _as_datetime(st["updated_at"]) or created,
        })

    for tid, tg in tags.items():
        tag_remap[tid] = uuid.uuid4()
        tag_rows.append({"id": tag_remap[tid], "name": tg["name"],
                         "color": tg["color"], "created_at": now, "updated_at": now})

    for cid, c in classes.items():
        class_remap[cid] = uuid.uuid4()
        class_rows.append({
            "id": class_remap[cid], "name": c["name"],
            "grade_level": c["grade_level"], "academic_year": c["academic_year"],
            "homeroom_person_id": user_person.get(c["homeroom_teacher_id"]),
            "created_at": now, "updated_at": now,
        })

    for en in enrollments.values():
        enrollment_rows.append({
            "id": uuid.uuid4(),
            "person_id": student_person[en["student_id"]],
            "class_id": class_remap[en["class_id"]],
            "valid_from": _as_date(en["valid_from"]),
            "valid_to": _as_date(en["valid_to"]),
            "reason": en["reason"],
        })

    # exams → sitting Events + score Events
    for xid, x in exams.items():
        exam_event_id = uuid.uuid4()
        start = datetime.combine(_as_date(x["exam_date"]), EXAM_HOUR)
        event_rows.append({
            "id": exam_event_id, "type": "exam", "title": x["name"],
            "description": None, "start_time": start,
            "end_time": None, "location": None,
            "payload": {"full_scores": {s["subject"]: s["full_score"]
                                        for s in subjects_by_exam.get(xid, [])}},
            "created_at": now, "updated_at": now,
        })
        # attendees: the students holding results for this sitting
        for pid in {student_person[r["student_id"]]
                    for r in results_by_exam.get(xid, [])}:
            person_event_rows.append({"person_id": pid, "event_id": exam_event_id})

        for r in results_by_exam.get(xid, []):
            subject = subject_by_id[r["exam_subject_id"]]
            absent = r["status"] == "absent"
            payload = {"subject": subject["subject"],
                       "max_score": subject["full_score"]}
            if absent:
                payload["absent"] = True  # convention: no "score" key when absent
            else:
                payload["score"] = r["score"]
                payload["absent"] = False
            event_id = uuid.uuid4()
            created = _as_datetime(r["created_at"]) or now  # legacy entry time
            event_rows.append({
                "id": event_id, "type": "score",
                "title": f"{x['name']}·{subject['subject']}",
                "description": None, "start_time": start,
                "end_time": None, "location": None, "payload": payload,
                "created_at": created,
                "updated_at": _as_datetime(r["updated_at"]) or created,
            })
            person_event_rows.append({
                "person_id": student_person[r["student_id"]], "event_id": event_id,
            })

    # manual timeline → Events 1:1, payload passed through free-form
    for ev in student_events:
        payload = _as_dict(ev["payload"])
        event_id = uuid.uuid4()
        event_rows.append({
            "id": event_id, "type": ev["event_type"],
            "title": payload.get("title") or ev["event_type"],
            "description": payload.get("description"),
            "start_time": _as_datetime(ev["occurred_at"]),
            "end_time": None, "location": None,
            "payload": payload,
            "created_at": now, "updated_at": now,
        })
        pid = student_person.get(ev["student_id"])
        if pid is not None:
            person_event_rows.append({"person_id": pid, "event_id": event_id})

    for st in student_tags:
        person_tag_rows.append({
            "person_id": student_person[st["student_id"]],
            "tag_id": tag_remap[st["tag_id"]],
        })

    for sess in auth_sessions:
        pid = user_person.get(sess["user_id"])
        if pid is None:
            continue  # token for an unknown account — dropped
        session_rows.append({
            "token": sess["token"], "person_id": pid,
            "created_at": _as_datetime(sess["created_at"]) or now,
        })

    # FK-safe insert order
    t_person = _t("person",
                  sa.column("id", sa.Uuid()), sa.column("phone", sa.String(40)),
                  sa.column("password_hash", sa.String(200)),
                  sa.column("email", sa.String(200)), sa.column("payload", JSONType),
                  sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime))
    t_tag = _t("tag", sa.column("id", sa.Uuid()), sa.column("name", sa.String(40)),
               sa.column("color", sa.String(20)), sa.column("created_at", sa.DateTime),
               sa.column("updated_at", sa.DateTime))
    t_class = _t("class", sa.column("id", sa.Uuid()), sa.column("name", sa.String(50)),
                 sa.column("grade_level", sa.Integer),
                 sa.column("academic_year", sa.String(20)),
                 sa.column("homeroom_person_id", sa.Uuid()),
                 sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime))
    t_enrollment = _t("enrollment", sa.column("id", sa.Uuid()),
                      sa.column("person_id", sa.Uuid()), sa.column("class_id", sa.Uuid()),
                      sa.column("valid_from", sa.Date), sa.column("valid_to", sa.Date),
                      sa.column("reason", sa.String(50)))
    t_event = _t("event", sa.column("id", sa.Uuid()), sa.column("type", sa.String(40)),
                 sa.column("title", sa.String(100)), sa.column("description", sa.Text),
                 sa.column("start_time", sa.DateTime), sa.column("end_time", sa.DateTime),
                 sa.column("location", sa.String(200)), sa.column("payload", JSONType),
                 sa.column("created_at", sa.DateTime), sa.column("updated_at", sa.DateTime))
    t_person_events = _t("person_events", sa.column("person_id", sa.Uuid()),
                         sa.column("event_id", sa.Uuid()))
    t_person_tags = _t("person_tags", sa.column("person_id", sa.Uuid()),
                       sa.column("tag_id", sa.Uuid()))
    t_auth_session = _t("auth_session", sa.column("token", sa.String(64)),
                        sa.column("person_id", sa.Uuid()),
                        sa.column("created_at", sa.DateTime))

    for table, rows in (
        (t_person, person_rows), (t_tag, tag_rows), (t_class, class_rows),
        (t_enrollment, enrollment_rows), (t_event, event_rows),
        (t_person_events, person_event_rows), (t_person_tags, person_tag_rows),
        (t_auth_session, session_rows),
    ):
        if rows:
            conn.execute(table.insert(), rows)


def downgrade() -> None:
    """Refuse: the event schema holds no per-column image of the legacy rows
    (free-form payloads, throwaway student hashes, dropped actor/ref columns).
    Restore the pre-migration backup instead."""
    raise NotImplementedError("payload → columns is lossy; restore from backup instead")
