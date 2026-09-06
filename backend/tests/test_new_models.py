import uuid
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import app.models as m
from app.database import Base


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = Session(eng)
    yield s
    s.close()
    eng.dispose()  # close the pooled sqlite3 connection (ResourceWarning under -W error)


def test_legacy_event_types_are_valid(db):
    ev = m.Event(type="talk", title="谈话", start_time=datetime(2026, 9, 5, 10, 0))
    db.add(ev)
    db.commit()
    assert ev.id is not None


def test_student_person_has_no_phone(db):
    # name lives on the typed column; the payload carries only role-specific data
    p = m.Person(name="王明", password_hash="x",
                 payload={"role": "student", "admission_no": "S1"})
    db.add(p)
    db.commit()
    assert p.phone is None
    assert p.name == "王明"
