"""Student roster import/export through .xlsx only."""
from __future__ import annotations

import io
import uuid
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from app.models import AuthSession, Class, Enrollment, Event, Person
from app.payloads import validate_person_payload
from app.routers import data
from app.security import hash_password
from app.unassigned import ensure_unassigned_class, is_unassigned_class
from tests.conftest import seed_person, seed_token

TEACHER_TOKEN = "d" * 64
AUTH = {"Authorization": f"Bearer {TEACHER_TOKEN}"}
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _student(db, name: str, admission_no: str, gender: str | None = None,
             birth_date: str | None = None) -> Person:
    p = Person(
        name=name,
        password_hash=hash_password("123456"),
        payload=validate_person_payload(
            "student",
            {"admission_no": admission_no, "gender": gender, "birth_date": birth_date},
        ),
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def client(make_client, db):
    tc = make_client(data.router)
    teacher = seed_person(db, "13800000001", name="陈老师")
    seed_token(db, teacher, TEACHER_TOKEN)
    db.commit()
    return tc


def _sample_workbook(title: str = "2025级707班花名册", remarks: bool = False) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append([title])
    ws.append(["学号", "姓名", "性别"] + (["备注"] if remarks else []))
    ws.append(["2025070701", "吴梓涵", "女"] + ([""] if remarks else []))
    ws.append(["2025070702", "邢宇辰", "男"] + (["流感"] if remarks else []))
    ws.append([2025070703, "卢梓扬", "男"])
    return wb


def _xlsx_bytes(wb: Workbook) -> bytes:
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload(client, content: bytes, **fields):
    return client.post(
        "/api/data/import/roster",
        files={"file": ("roster.xlsx", content, XLSX_MIME)},
        data={k: str(v) for k, v in fields.items()},
        headers=AUTH,
    )


def _students(db):
    return db.query(Person).filter(
        Person.payload["role"].as_string() == "student"
    ).all()


def _unassigned(db):
    return ensure_unassigned_class(db)


def test_roster_import_to_unassigned_by_default(client, db):
    res = _upload(client, _xlsx_bytes(_sample_workbook()))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 3
    assert body["updated"] == 0
    assert body["errors"] == []
    assert body["target_class"] is None

    unassigned = _unassigned(db)
    students = _students(db)
    assert {s.name for s in students} == {"吴梓涵", "邢宇辰", "卢梓扬"}
    wu = next(s for s in students if s.name == "吴梓涵")
    assert wu.payload["gender"] == "F"
    assert all(
        db.query(Enrollment).filter(
            Enrollment.person_id == s.id,
            Enrollment.class_id == unassigned.id,
            Enrollment.valid_to.is_(None),
        ).count() == 1
        for s in students
    )
    assert db.query(Event).filter(Event.type == "enrolled").count() == 3


def test_roster_import_into_existing_class(client, db):
    klass = Class(name="707班", grade_level=7, academic_year="2025")
    db.add(klass)
    db.commit()

    res = _upload(client, _xlsx_bytes(_sample_workbook()), class_id=str(klass.id))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 3
    assert body["target_class"]["name"] == "707班"
    assert db.query(Class).filter(Class.name == "707班").count() == 1


def test_roster_import_updates_existing_without_moving_class(client, db):
    old = Class(name="七年级1班", grade_level=7, academic_year="2025/2026")
    db.add(old)
    db.flush()
    existing = _student(db, "吴梓涵", "2025070701", gender="M")
    db.add(Enrollment(person_id=existing.id, class_id=old.id,
                      valid_from=date(2025, 9, 1)))
    db.commit()

    res = _upload(client, _xlsx_bytes(_sample_workbook()))
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 2
    assert body["updated"] == 1
    enrollment = db.query(Enrollment).filter_by(person_id=existing.id).one()
    assert enrollment.class_id == old.id and enrollment.valid_to is None
    db.refresh(existing)
    assert existing.payload["gender"] == "F"


def test_roster_import_with_class_id_moves_existing(client, db):
    old = Class(name="七年级1班", grade_level=7, academic_year="2025/2026")
    target = Class(name="707班", grade_level=7, academic_year="2025")
    db.add_all([old, target])
    db.flush()
    existing = _student(db, "吴梓涵", "2025070701")
    db.add(Enrollment(person_id=existing.id, class_id=old.id,
                      valid_from=date(2025, 9, 1)))
    db.commit()

    res = _upload(client, _xlsx_bytes(_sample_workbook()), class_id=str(target.id))
    assert res.status_code == 200
    enrollment = db.query(Enrollment).filter(
        Enrollment.person_id == existing.id, Enrollment.valid_to.is_(None)
    ).one()
    assert enrollment.class_id == target.id


def test_roster_reimport_updates_without_duplicates(client, db):
    first = _upload(client, _xlsx_bytes(_sample_workbook()))
    assert first.status_code == 200
    assert first.json()["created"] == 3

    second = _upload(client, _xlsx_bytes(_sample_workbook()))
    assert second.status_code == 200
    body = second.json()
    assert body["created"] == 0
    assert body["updated"] == 3
    assert db.query(Person).count() == 4  # teacher + 3 students


def test_roster_import_row_errors_and_ignored_columns(client, db):
    wb = Workbook()
    ws = wb.active
    ws.append(["2025级707班花名册"])
    ws.append(["学号", "姓名", "性别", "备注"])
    ws.append(["2025070701", "吴梓涵", "女", "流感"])
    ws.append(["", "无学号", "女", ""])
    ws.append(["2025070701", "学号重复", "男", ""])
    res = _upload(client, _xlsx_bytes(wb))
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 1
    assert body["ignored_columns"] == ["备注"]
    assert {e["message"] for e in body["errors"]} == {"缺少学号", "文件内学号重复"}


def test_roster_import_rejects_bad_gender(client, db):
    wb = Workbook()
    ws = wb.active
    ws.append(["花名册"])
    ws.append(["学号", "姓名", "性别"])
    ws.append(["2025070701", "吴梓涵", "未知"])
    res = _upload(client, _xlsx_bytes(wb))
    assert res.status_code == 200
    body = res.json()
    assert body["created"] == 0
    assert body["errors"][0]["message"] == "无法识别的性别: 未知"


def test_roster_import_without_header_fails(client, db):
    wb = Workbook()
    wb.active.append(["只有一行字"])
    res = _upload(client, _xlsx_bytes(wb))
    assert res.status_code == 400
    assert "未找到表头行" in res.json()["detail"]


def test_roster_export_roundtrip(client, db):
    klass = Class(name="707班", grade_level=7, academic_year="2025")
    db.add(klass)
    db.flush()
    _student(db, "吴梓涵", "2025070701", gender="F")
    _student(db, "邢宇辰", "2025070702", gender="M")
    for s in _students(db):
        db.add(Enrollment(person_id=s.id, class_id=klass.id, valid_from=date(2025, 9, 1)))
    db.commit()

    res = client.get(f"/api/data/export/roster?class_id={klass.id}", headers=AUTH)
    assert res.status_code == 200
    ws = load_workbook(io.BytesIO(res.content)).active
    assert ws.cell(3, 1).value == "2025070701" and ws.cell(3, 2).value == "吴梓涵"
    assert ws.cell(3, 3).value == "女"
    assert ws.cell(4, 3).value == "男"

    res2 = _upload(client, res.content)
    assert res2.status_code == 200
    body = res2.json()
    assert body["created"] == 0
    assert body["updated"] == 2
    unassigned = _unassigned(db)
    still_in_class = db.query(Enrollment).filter(
        Enrollment.valid_to.is_(None),
        Enrollment.class_id == klass.id,
    ).count()
    assert still_in_class == 2
    assert not is_unassigned_class(klass)


def test_roster_export_unassigned_class_404(client, db):
    unassigned = _unassigned(db)
    db.commit()
    res = client.get(f"/api/data/export/roster?class_id={unassigned.id}", headers=AUTH)
    assert res.status_code == 404


def test_roster_template_download(client):
    res = client.get("/api/data/export/roster-template", headers=AUTH)
    assert res.status_code == 200
    ws = load_workbook(io.BytesIO(res.content)).active
    assert [ws.cell(2, c).value for c in (1, 2, 3)] == ["学号", "姓名", "性别"]


def test_demo_seed_loads_dataset(client, db):
    res = client.post("/api/data/demo/seed", headers=AUTH)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["teacher"]["phone"] == "13800000001"
    students = _students(db)
    assert len(students) >= 20
    assert db.query(Class).filter(Class.name == "七年级1班").count() == 1
    assert db.query(Event).filter(Event.type == "exam").count() >= 1
    assert db.query(AuthSession).filter(AuthSession.token == TEACHER_TOKEN).count() == 1
    assert db.query(Person).filter(Person.phone == "13800000000").count() == 0


def test_demo_seed_requires_teacher(client, db):
    from app.security import hash_password

    student = Person(
        name="林小明",
        password_hash=hash_password("123456"),
        payload=validate_person_payload("student", {"admission_no": "S999"}),
    )
    db.add(student)
    db.flush()
    token = "s" * 64
    db.add(AuthSession(token=token, person_id=student.id))
    db.commit()

    res = client.post("/api/data/demo/seed", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_demo_reset_clears_database(client, db):
    seed_res = client.post("/api/data/demo/seed", headers=AUTH)
    assert seed_res.status_code == 200
    assert _students(db)

    reset_res = client.post("/api/data/demo/reset", headers=AUTH)
    assert reset_res.status_code == 200
    assert reset_res.json()["ok"] is True
    assert db.query(Person).count() == 0
    assert db.query(Class).count() == 0
