# backend/tests/test_eventing.py
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import eventing
from app.database import Base
from app.models import Person


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    s = Session(eng)
    yield s
    s.close()
    eng.dispose()  # close the pooled sqlite3 connection (ResourceWarning under -W error)


@pytest.fixture()
def person(db):
    p = Person(name="王明", phone="13800000000", password_hash="x",
               payload={"role": "student", "admission_no": "S1",
                        "birth_date": "2012-05-14"})
    db.add(p)
    db.commit()
    return p


def test_create_event_links_attendees_and_validates(db, person):
    ev = eventing.create_event(
        db, event_type="home_visited", title="家访", start_time=datetime(2026, 8, 20, 15, 0),
        payload={"summary": "开学前家访"}, attendee_ids=[person.id], commit=True)
    assert ev.payload == {"summary": "开学前家访"}
    assert [a.id for a in ev.attendees] == [person.id]


def test_create_event_rejects_bad_payload(db, person):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        eventing.create_event(db, event_type="score", title="x",
                              start_time=datetime(2026, 9, 1),
                              payload={"subject": "数学"}, attendee_ids=[person.id])


def test_next_birthday_date_feb29():
    assert eventing.next_birthday_date(date(2012, 2, 29), today=date(2026, 1, 1)) == date(2026, 2, 28)
    assert eventing.next_birthday_date(date(2012, 2, 29), today=date(2026, 3, 1)) == date(2027, 2, 28)
