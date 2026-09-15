"""Workspace-id invariant guards.

Regression tests for the 2026-09-15 production incident: an admin-panel edit
rebuilt the teacher payload from scratch (wiping workspace_id) while the read
path minted a fresh random id per request, so every workspace page rendered
empty and the tagged students looked lost.
"""
from __future__ import annotations

import pytest

from app.models import Person
from app.payloads import validate_person_payload
from app.routers import admin, auth, exams
from app.security import hash_password
from app.workspace import (
    ensure_workspace_id,
    students_query,
    tag_student_workspace,
    workspace_id,
)
from tests.conftest import seed_person, seed_token

ADMIN_TOKEN = "a" * 64


def test_workspace_id_read_does_not_mint(db):
    """workspace_id() on a workspace-less teacher returns "" and persists
    nothing — minting on read forks the workspace per request."""
    teacher = seed_person(db, "read-mint@test.example")

    assert workspace_id(teacher) == ""
    assert workspace_id(teacher) == workspace_id(teacher)

    db.commit()
    db.refresh(teacher)
    assert not (teacher.payload or {}).get("workspace_id")


def test_students_query_empty_without_workspace(db):
    """A workspace-less teacher matches no students — not the untagged ones
    (an IS NULL-style fallback would leak other workspaces' rows)."""
    teacher = seed_person(db, "no-wid@test.example")
    seed_person(db, None, role="student", name="无主学生", admission_no="2026001")

    assert students_query(db, teacher).all() == []


def test_tag_student_workspace_persists_teacher_wid(db):
    """The write path mints once and both sides carry the same id after
    commit."""
    teacher = seed_person(db, "tag@test.example")
    student = seed_person(db, None, role="student", name="学生", admission_no="2026002")

    tag_student_workspace(student, teacher)
    wid = (teacher.payload or {}).get("workspace_id")
    assert wid

    db.commit()
    db.refresh(teacher)
    db.refresh(student)
    assert (teacher.payload or {}).get("workspace_id") == wid
    assert (student.payload or {}).get("workspace_id") == wid


def test_admin_patch_same_role_keeps_workspace_id(make_client, db):
    """Editing an account in the admin panel without changing its role must
    leave the payload (and the workspace_id) exactly as stored."""
    tc = make_client(auth.router, admin.router, auth_dependency=False)

    admin_p = seed_person(db, "admin-keep@test.example", role="admin", name="管理员")
    teacher = seed_person(db, "teacher-keep@test.example", name="陈老师")
    ensure_workspace_id(teacher)
    db.commit()
    wid = (teacher.payload or {}).get("workspace_id")
    seed_token(db, admin_p, ADMIN_TOKEN)

    resp = tc.patch(
        f"/api/admin/users/{teacher.id}",
        json={"role": "teacher"},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    assert resp.status_code == 200
    db.expire_all()
    assert (teacher.payload or {}).get("workspace_id") == wid

    # changing the password only must not rebuild the payload either
    resp = tc.patch(
        f"/api/admin/users/{teacher.id}",
        json={"password": "654321"},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    assert resp.status_code == 200
    db.expire_all()
    assert (teacher.payload or {}).get("workspace_id") == wid


def test_admin_patch_role_change_rebuilds_payload(make_client, db):
    """A real role change resets the payload to the new role's shape —
    documented behavior, locked here so it stays deliberate."""
    tc = make_client(auth.router, admin.router, auth_dependency=False)

    admin_p = seed_person(db, "admin-change@test.example", role="admin", name="管理员")
    teacher = seed_person(db, "teacher-change@test.example", name="陈老师")
    ensure_workspace_id(teacher)
    db.commit()
    seed_token(db, admin_p, ADMIN_TOKEN)

    resp = tc.patch(
        f"/api/admin/users/{teacher.id}",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
    )
    assert resp.status_code == 200
    db.expire_all()
    assert teacher.payload == validate_person_payload("admin", {})
    assert (teacher.payload or {}).get("workspace_id") is None


def test_create_exam_mints_and_stamps_workspace(make_client, db):
    """create_exam is a write path: a workspace-less teacher gets an id
    minted, the exam stamped with it, and both survive the endpoint commit —
    otherwise the sitting would be orphaned and invisible forever."""
    from app.models import Event

    tc = make_client(exams.router, auth_dependency=False)
    teacher = seed_person(db, "exam-mint@test.example")
    token = seed_token(db, teacher, "e" * 64)

    resp = tc.post(
        "/api/exams",
        json={
            "name": "期中考试",
            "exam_date": "2026-10-12",
            "subjects": [{"subject": "math", "full_score": 100}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text

    db.expire_all()
    db.refresh(teacher)
    wid = (teacher.payload or {}).get("workspace_id")
    assert wid
    ev = db.query(Event).filter(Event.type == "exam").one()
    assert (ev.payload or {}).get("workspace_id") == wid
