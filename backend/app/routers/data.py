"""Student roster import/export through .xlsx only.

Roster (POST /data/import/roster, GET /data/export/roster[/-template]) moves
student rows through .xlsx in the format schools actually hand out: an optional
merged title row ("…班花名册"), a header row (学号/姓名/性别[/出生日期/…]) and
one student per row. Import creates or updates students only — it never
creates classes. New rows land in the system unassigned class unless an
existing class_id is supplied; re-import without class_id updates fields in
place without moving enrollments.
"""
from __future__ import annotations

import datetime as dt
import io
import uuid as uuid_mod
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..deps import get_current_person
from ..eventing import create_event
from ..gender import gender_label, parse_gender
from ..models import AuthSession, Class, Enrollment, Person
from ..models._common import utcnow
from ..payloads import validate_person_payload
from ..security import hash_password
from ..seed import seed
from ..unassigned import class_for_api, ensure_unassigned_class, is_unassigned_class
from ..workspace import tag_student_workspace

router = APIRouter(
    tags=["data"],
    dependencies=[Depends(get_current_person)],
)

_bearer = HTTPBearer(auto_error=False)

_HEADER_ALIASES = {
    "admission_no": {"学号", "学籍号", "学籍编号", "学籍辅号", "学籍"},
    "name": {"姓名", "名字", "学生姓名"},
    "gender": {"性别"},
    "birth_date": {"出生日期", "出生年月", "生日"},
}
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ROSTER_HEADERS = ["学号", "姓名", "性别"]


def _cell_str(value) -> str:
    """Excel cells arrive typed: 2025070701 as float, dates as datetime."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _parse_birth_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y%m%d"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"无法识别的出生日期: {text}")


def _locate_header(rows) -> tuple[int, dict[str, int]]:
    """Find the header row within the first 10 rows and map field -> column."""
    for idx, row in enumerate(rows[:10]):
        cells = [_cell_str(c) for c in row]
        mapping = {}
        for field, aliases in _HEADER_ALIASES.items():
            for col, cell in enumerate(cells):
                if cell in aliases:
                    mapping[field] = col
                    break
        if "admission_no" in mapping and "name" in mapping:
            return idx, mapping
    raise HTTPException(status_code=400, detail="未找到表头行（需同时包含“学号”和“姓名”列）")


def _resolve_target_class(db: Session, class_id: uuid_mod.UUID | None, user: Person) -> Class:
    if class_id is None:
        return ensure_unassigned_class(db)
    cls = db.get(Class, class_id)
    # 工作区班级只允许归属教师导入；无主班级（历史数据/夹具）保持兼容。
    if cls is None or is_unassigned_class(cls):
        raise HTTPException(status_code=404, detail="class not found")
    if cls.teacher_id is not None and cls.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="class not found")
    return cls


def _move_student(
    db: Session,
    person_row: Person,
    target: Class,
    *,
    reason: str,
    today: dt.date,
) -> None:
    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.person_id == person_row.id, Enrollment.valid_to.is_(None))
        .first()
    )
    current_id = enrollment.class_id if enrollment else None
    if current_id == target.id:
        return
    if enrollment is not None:
        enrollment.valid_to = today
        enrollment.reason = "moved"
    db.add(
        Enrollment(
            person_id=person_row.id,
            class_id=target.id,
            valid_from=today,
            reason=reason,
        )
    )


def _wipe_db(bind=engine) -> None:
    Base.metadata.drop_all(bind=bind)
    Base.metadata.create_all(bind=bind)


def _require_teacher(user: Person) -> None:
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="仅教师账号可使用演示数据功能")


def _teacher_snapshot(user: Person) -> dict:
    payload = dict(user.payload or {})
    payload.pop("semesters", None)
    return {
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "password_hash": user.password_hash,
        "payload": validate_person_payload("teacher", payload),
    }


def _rebind_teacher_workspace(
    db: Session,
    user: Person,
    token: str,
    *,
    load_seed: bool,
) -> Person:
    """Wipe business data, keep the current teacher account and bearer session."""
    teacher_snap = _teacher_snapshot(user)
    _wipe_db(db.get_bind())
    db.rollback()
    db.expire_all()
    db.expunge(user)
    ensure_unassigned_class(db)
    teacher = Person(**teacher_snap)
    db.add(teacher)
    db.flush()
    if load_seed:
        seed(db, teacher=teacher, include_admin=False)
    db.add(AuthSession(token=token, person_id=teacher.id))
    return teacher


@router.post("/data/demo/seed")
def load_demo_data(
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Wipe app data and load demo content bound to the current teacher."""
    _require_teacher(user)
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        teacher = _rebind_teacher_workspace(
            db, user, credentials.credentials, load_seed=True
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"加载演示数据失败: {exc}") from exc
    return {
        "ok": True,
        "teacher": {"name": teacher.name, "phone": teacher.phone},
    }


@router.post("/data/demo/reset")
def reset_app_data(
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Clear all business data but keep the current teacher signed in."""
    _require_teacher(user)
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        teacher = _rebind_teacher_workspace(
            db, user, credentials.credentials, load_seed=False
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"重置失败: {exc}") from exc
    return {
        "ok": True,
        "teacher": {"name": teacher.name, "phone": teacher.phone},
    }


@router.post("/data/import/roster")
async def import_roster(
    file: UploadFile = File(...),
    class_id: uuid_mod.UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    user: Person = Depends(get_current_person),
):
    """Import student rows from xlsx. Updates existing students by admission_no.
    Optional class_id assigns imported rows to that class; otherwise new students
    go to the system unassigned class and existing enrollments are left alone."""
    content = await file.read()
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析该 Excel 文件，请提供 .xlsx 格式")
    try:
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    header_idx, columns = _locate_header(rows)
    ignored = sorted(
        {_cell_str(c) for row in rows[header_idx : header_idx + 1] for c in row if _cell_str(c)}
        - set().union(*_HEADER_ALIASES.values())
    )

    assign_class = class_id is not None
    target_cls = _resolve_target_class(db, class_id, user)
    today = dt.date.today()
    report: list[dict] = []
    seen_in_file: set[str] = set()
    created = updated = 0
    for pos, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        values = {
            field: (_cell_str(row[col]) if col < len(row) else "")
            for field, col in columns.items()
        }
        admission_no = values.get("admission_no", "")
        name = values.get("name", "")
        if not admission_no and not name:
            continue
        item = {"row": pos, "admission_no": admission_no, "name": name, "status": "ok"}
        try:
            if not admission_no:
                raise ValueError("缺少学号")
            if not name:
                raise ValueError("缺少姓名")
            if admission_no in seen_in_file:
                raise ValueError("文件内学号重复")
            seen_in_file.add(admission_no)

            gender_raw = values.get("gender") or None
            gender = parse_gender(gender_raw) if gender_raw else None
            birth_raw = (
                row[columns["birth_date"]]
                if "birth_date" in columns and columns["birth_date"] < len(row)
                else None
            )
            try:
                birth_date = _parse_birth_date(birth_raw)
                item["message"] = None
            except ValueError as exc:
                birth_date, item["message"] = None, str(exc)

            person_row = (
                db.query(Person)
                .filter(
                    Person.payload["role"].as_string() == "student",
                    Person.payload["admission_no"].as_string() == admission_no,
                )
                .first()
            )
            if person_row is None:
                payload = validate_person_payload(
                    "student",
                    {
                        "admission_no": admission_no,
                        "gender": gender,
                        "birth_date": birth_date.isoformat() if birth_date else None,
                    },
                )
                person_row = Person(
                    name=name,
                    password_hash=hash_password(uuid_mod.uuid4().hex),
                    payload=payload,
                )
                db.add(person_row)
                db.flush()
                tag_student_workspace(person_row, user)
                _move_student(db, person_row, target_cls, reason="admitted", today=today)
                create_event(
                    db,
                    event_type="enrolled",
                    title="入学",
                    start_time=utcnow(),
                    payload=(
                        {} if is_unassigned_class(target_cls)
                        else {"class_name": target_cls.name}
                    ),
                    attendee_ids=[person_row.id],
                )
                created += 1
                item["status"] = "created"
            else:
                person_row.name = name
                payload = dict(person_row.payload or {})
                if gender is not None:
                    payload["gender"] = gender
                if birth_date:
                    payload["birth_date"] = birth_date.isoformat()
                person_row.payload = validate_person_payload("student", payload)
                if assign_class:
                    _move_student(db, person_row, target_cls, reason="moved", today=today)
                updated += 1
                item["status"] = "updated"
        except ValueError as exc:
            item["status"] = "error"
            item["message"] = str(exc)
        report.append(item)

    errors = [r for r in report if r["status"] == "error"]
    db.commit()
    return {
        "target_class": class_for_api(target_cls),
        "created": created,
        "updated": updated,
        "errors": errors,
        "ignored_columns": ignored,
        "rows": report,
    }


def _roster_workbook(cls: Class, students: list[Person]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "花名册"
    ws.append([f"{cls.academic_year}级{cls.name}花名册"])
    ws.append(_ROSTER_HEADERS)
    for s in students:
        payload = s.payload or {}
        ws.append([
            payload.get("admission_no") or "",
            s.name,
            gender_label(payload.get("gender")),
        ])
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 8
    bold = Font(bold=True)
    ws.cell(row=1, column=1).font = bold
    for col in range(1, len(_ROSTER_HEADERS) + 1):
        ws.cell(row=2, column=col).font = bold
    return wb


def _xlsx_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    quoted = quote(filename)
    return StreamingResponse(
        buf,
        media_type=_XLSX_MIME,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


@router.get("/data/export/roster")
def export_roster(class_id: uuid_mod.UUID, db: Session = Depends(get_db)):
    """Export one class's current roster in the import-compatible format."""
    cls = db.get(Class, class_id)
    if cls is None or is_unassigned_class(cls):
        raise HTTPException(status_code=404, detail="class not found")
    students = (
        db.query(Person)
        .join(Enrollment, Enrollment.person_id == Person.id)
        .filter(Enrollment.class_id == cls.id, Enrollment.valid_to.is_(None))
        .order_by(Person.payload["admission_no"].as_string())
        .all()
    )
    return _xlsx_response(
        _roster_workbook(cls, students),
        f"{cls.academic_year}级{cls.name}花名册.xlsx",
    )


@router.get("/data/export/roster-template")
def export_roster_template():
    """Blank roster template in the import-compatible format."""
    wb = Workbook()
    ws = wb.active
    ws.title = "花名册"
    ws.append(["班级花名册"])
    ws.append(_ROSTER_HEADERS)
    ws.append(["2025070701", "张三", "男"])
    ws.append(["2025070702", "李四", "女"])
    return _xlsx_response(wb, "花名册模板.xlsx")
