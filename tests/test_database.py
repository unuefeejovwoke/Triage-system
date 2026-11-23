"""Tests for the database schema and seed script.

These use a temporary in-memory SQLite database, so they never touch your
real PostgreSQL data.
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CareAdvice, Consultation, Disposition, Protocol, TriageQuestion, User
from scripts.seed import seed_dispositions, seed_protocols


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def seeded(db):
    d = seed_dispositions(db)
    seed_protocols(db, d)
    db.commit()
    return d


def test_seed_loads_everything(db):
    seeded(db)
    assert db.query(Disposition).count() == 4
    assert db.query(Protocol).count() == 10
    assert db.query(TriageQuestion).count() == 78
    assert db.query(CareAdvice).count() >= 30


def test_seed_twice_does_not_duplicate(db):
    d = seeded(db)
    added, skipped = seed_protocols(db, d)
    assert (added, skipped) == (0, 10)


def test_questions_come_back_in_order(db):
    seeded(db)
    p = db.scalar(select(Protocol).where(Protocol.name == "Chest Pain"))
    assert [q.question_order for q in p.questions] == list(range(1, 8))
    assert p.questions[0].disposition.level == "emergency"


def test_override_without_reason_is_blocked(db):
    seeded(db)
    nurse = User(full_name="Test Nurse", email="n@test.local", password_hash="x", role="nurse")
    db.add(nurse)
    db.flush()
    db.add(Consultation(user_id=nurse.user_id, caller_ref="C-000001", caller_age=40,
                        caller_sex="male", consent_given=True, overridden=True, override_reason=None))
    with pytest.raises(IntegrityError):
        db.flush()


def test_invalid_role_is_blocked(db):
    db.add(User(full_name="X", email="x@test.local", password_hash="x", role="doctor"))
    with pytest.raises(IntegrityError):
        db.flush()
