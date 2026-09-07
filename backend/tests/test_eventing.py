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


def test_birthday_in_month():
    assert eventing.birthday_in_month(date(2012, 5, 14), 2026, 5) == date(2026, 5, 14)
    assert eventing.birthday_in_month(date(2012, 5, 14), 2026, 6) is None
    assert eventing.birthday_in_month(date(2012, 2, 29), 2026, 2) == date(2026, 2, 28)


def test_sync_birthday_event_creates_and_removes(db, person):
    from app.models import Event

    eventing.sync_birthday_event(db, person)
    db.commit()
    assert db.query(Event).filter(Event.type == "birthday").count() == 1

    payload = dict(person.payload or {})
    payload["is_active"] = False
    person.payload = payload
    eventing.sync_birthday_event(db, person)
    db.commit()
    assert db.query(Event).filter(Event.type == "birthday").count() == 0


def test_sync_birthday_event_updates_instead_of_duplicating(db, person):
    from app.models import Event

    eventing.sync_birthday_event(db, person)
    eventing.sync_birthday_event(db, person)
    db.commit()
    assert db.query(Event).filter(Event.type == "birthday").count() == 1

    person.payload = {**(person.payload or {}), "birth_date": "2013-06-01"}
    eventing.sync_birthday_event(db, person)
    db.commit()
    rows = db.query(Event).filter(Event.type == "birthday").all()
    assert len(rows) == 1
    assert rows[0].payload == {"birth_date": "2013-06-01"}


def test_dedupe_birthday_events_removes_extras(db, person):
    from app.models import Event

    eventing.create_event(
        db,
        event_type="birthday",
        title="生日",
        start_time=datetime(2026, 5, 14, 9, 0),
        payload={"birth_date": "2012-05-14"},
        attendee_ids=[person.id],
    )
    eventing.create_event(
        db,
        event_type="birthday",
        title="生日",
        start_time=datetime(2026, 5, 14, 9, 0),
        payload={"birth_date": "2012-05-14"},
        attendee_ids=[person.id],
    )
    db.commit()
    assert db.query(Event).filter(Event.type == "birthday").count() == 2

    eventing.dedupe_birthday_events(db)
    eventing.sync_birthday_event(db, person)
    db.commit()
    assert db.query(Event).filter(Event.type == "birthday").count() == 1
