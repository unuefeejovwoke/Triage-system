"""Tests for the backend API. Uses a temporary in-memory database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import AuditLog, Protocol, User
from app.security import hash_password
from scripts.seed import seed_dispositions, seed_protocols

PASSWORD = "Password123"


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestSession() as db:
        seed_protocols(db, seed_dispositions(db))
        db.add_all([
            User(full_name="Admin User", email="admin@example.com", password_hash=hash_password(PASSWORD), role="admin"),
            User(full_name="Nurse One", email="nurse1@example.com", password_hash=hash_password(PASSWORD), role="nurse"),
            User(full_name="Nurse Two", email="nurse2@example.com", password_hash=hash_password(PASSWORD), role="nurse"),
        ])
        db.commit()

    def override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    c = TestClient(app)
    c.session = TestSession
    yield c
    app.dependency_overrides.clear()


def login(client, email, password=PASSWORD):
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def protocol_id(client, name):
    with client.session() as db:
        return db.scalar(select(Protocol.protocol_id).where(Protocol.name == name))


def start(client, h, name="Chest Pain", consent=True):
    return client.post("/consultations", headers=h, json={
        "caller_age": 58, "caller_sex": "male", "consent_given": consent, "protocol_id": protocol_id(client, name)})


def answer_through(client, h, cid, step, yes_orders):
    """Answer questions in order until a result is reached."""
    while not step["done"]:
        q = step["question"]
        r = client.post(f"/consultations/{cid}/answers", headers=h,
                        json={"question_id": q["question_id"], "answer": q["order"] in yes_orders})
        assert r.status_code == 200, r.text
        step = r.json()
    return step


# ---------------------------------------------------------------- login and access

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_login_works_and_wrong_password_fails(client):
    login(client, "nurse1@example.com")
    r = client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_is_case_insensitive_for_email(client):
    login(client, "NURSE1@Example.COM")


def test_endpoints_need_login(client):
    for path in ["/protocols", "/consultations", "/admin/users", "/auth/me"]:
        assert client.get(path).status_code == 401


def test_bad_token_is_rejected(client):
    assert client.get("/protocols", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401


def test_nurse_cannot_use_admin_endpoints(client):
    h = login(client, "nurse1@example.com")
    assert client.get("/admin/users", headers=h).status_code == 403
    assert client.get("/admin/audit-logs", headers=h).status_code == 403


def test_deactivated_user_cannot_log_in(client):
    admin = login(client, "admin@example.com")
    nurse_id = next(u["user_id"] for u in client.get("/admin/users", headers=admin).json()
                    if u["email"] == "nurse2@example.com")
    assert client.patch(f"/admin/users/{nurse_id}", headers=admin, json={"is_active": False}).status_code == 200
    r = client.post("/auth/login", data={"username": "nurse2@example.com", "password": PASSWORD})
    assert r.status_code == 401


# ---------------------------------------------------------------- protocols

def test_nurse_can_list_and_open_protocols(client):
    h = login(client, "nurse1@example.com")
    protocols = client.get("/protocols", headers=h).json()
    assert len(protocols) == 10
    detail = client.get(f"/protocols/{protocols[0]['protocol_id']}", headers=h).json()
    assert detail["questions"][0]["order"] == 1
    assert "self_care" in detail["advice"]


# ---------------------------------------------------------------- consultation flow

def test_full_call_emergency_accepted(client):
    h = login(client, "nurse1@example.com")
    r = start(client, h)
    assert r.status_code == 201
    c = r.json()
    assert c["caller_ref"].startswith("C-") and c["step"]["number"] == 1
    result = answer_through(client, h, c["consultation_id"], c["step"], yes_orders={4})
    assert result["level"] == "emergency" and result["triggered_by"]["order"] == 4
    assert result["questions_asked"] == 4
    saved = client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={"accept": True}).json()
    assert saved["final_level"] == "emergency" and saved["overridden"] is False and saved["ended_at"]
    assert len(saved["answers"]) == 4


def test_all_no_gives_self_care(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h, "Headache").json()
    result = answer_through(client, h, c["consultation_id"], c["step"], yes_orders=set())
    assert result["level"] == "self_care" and result["triggered_by"] is None


def test_no_consent_stores_nothing(client):
    h = login(client, "nurse1@example.com")
    r = start(client, h, consent=False)
    assert r.status_code == 400 and "No data is stored" in r.json()["detail"]
    assert client.get("/consultations", headers=h).json() == []


def test_cannot_skip_a_question(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    detail = client.get(f"/protocols/{protocol_id(client, 'Chest Pain')}", headers=h).json()
    q3 = detail["questions"][2]["question_id"]
    r = client.post(f"/consultations/{c['consultation_id']}/answers", headers=h, json={"question_id": q3, "answer": True})
    assert r.status_code == 409


def test_back_undoes_last_answer(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    q1 = c["step"]["question"]
    step = client.post(f"/consultations/{c['consultation_id']}/answers", headers=h,
                       json={"question_id": q1["question_id"], "answer": False}).json()
    assert step["number"] == 2
    back = client.delete(f"/consultations/{c['consultation_id']}/answers/last", headers=h).json()
    assert back["number"] == 1


def test_cannot_finalize_before_result(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    r = client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={"accept": True})
    assert r.status_code == 409


def test_override_requires_reason(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    answer_through(client, h, c["consultation_id"], c["step"], yes_orders={7})
    r = client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h,
                    json={"accept": False, "override_level": "urgent"})
    assert r.status_code == 422


def test_override_with_reason_is_saved_and_logged(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    answer_through(client, h, c["consultation_id"], c["step"], yes_orders={7})
    saved = client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={
        "accept": False, "override_level": "urgent", "override_reason": "Caller sounds very anxious and is alone."}).json()
    assert saved["final_level"] == "urgent" and saved["overridden"] is True
    assert saved["override_reason"].startswith("Caller sounds")
    admin = login(client, "admin@example.com")
    actions = [a["action"] for a in client.get("/admin/audit-logs", headers=admin).json()]
    assert "disposition_overridden" in actions


def test_closed_consultation_cannot_be_changed(client):
    h = login(client, "nurse1@example.com")
    c = start(client, h).json()
    answer_through(client, h, c["consultation_id"], c["step"], yes_orders={1})
    client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={"accept": True})
    r = client.delete(f"/consultations/{c['consultation_id']}/answers/last", headers=h)
    assert r.status_code == 409


def test_nurse_sees_only_own_consultations_admin_sees_all(client):
    n1, n2, admin = (login(client, e) for e in ["nurse1@example.com", "nurse2@example.com", "admin@example.com"])
    c1 = start(client, n1).json()
    start(client, n2)
    assert len(client.get("/consultations", headers=n1).json()) == 1
    assert client.get(f"/consultations/{c1['consultation_id']}", headers=n2).status_code == 403
    assert len(client.get("/consultations", headers=admin).json()) == 2


def test_admin_cannot_answer_questions(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    c = start(client, n1).json()
    r = client.post(f"/consultations/{c['consultation_id']}/answers", headers=admin,
                    json={"question_id": c["step"]["question"]["question_id"], "answer": False})
    assert r.status_code == 403


# ---------------------------------------------------------------- admin

def test_admin_creates_user_who_can_log_in(client):
    admin = login(client, "admin@example.com")
    r = client.post("/admin/users", headers=admin, json={
        "full_name": "New Nurse", "email": "new@example.com", "password": "SafePass99", "role": "nurse"})
    assert r.status_code == 201
    login(client, "new@example.com", "SafePass99")
    dup = client.post("/admin/users", headers=admin, json={
        "full_name": "Dup", "email": "NEW@example.com", "password": "SafePass99"})
    assert dup.status_code == 409


def test_admin_cannot_deactivate_self(client):
    admin = login(client, "admin@example.com")
    me = client.get("/auth/me", headers=admin).json()
    assert client.patch(f"/admin/users/{me['user_id']}", headers=admin, json={"is_active": False}).status_code == 409


NEW_PROTOCOL = {
    "name": "Eye Injury", "version": "1.0", "population": "adult", "source_guidance": "Test guidance",
    "questions": [
        {"order": 1, "text": "Chemical in the eye?", "disposition": "emergency"},
        {"order": 2, "text": "Blurred vision?", "disposition": "urgent"},
    ],
    "advice": {"emergency": ["Rinse with water and call 112."], "urgent": ["Go to a clinic today."],
               "self_care": ["Rest the eye."]},
}


def test_admin_creates_protocol(client):
    admin = login(client, "admin@example.com")
    r = client.post("/admin/protocols", headers=admin, json=NEW_PROTOCOL)
    assert r.status_code == 201 and len(r.json()["questions"]) == 2
    assert len(client.get("/protocols", headers=admin).json()) == 11


def test_unsafe_protocol_is_rejected_by_api(client):
    admin = login(client, "admin@example.com")
    bad = {**NEW_PROTOCOL, "questions": [
        {"order": 1, "text": "Blurred vision?", "disposition": "urgent"},
        {"order": 2, "text": "Chemical in the eye?", "disposition": "emergency"}]}
    r = client.post("/admin/protocols", headers=admin, json=bad)
    assert r.status_code == 422
    assert "less serious" in str(r.json()["detail"]["problems"])


def test_protocol_in_use_cannot_be_edited(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    start(client, n1)
    pid = protocol_id(client, "Chest Pain")
    r = client.put(f"/admin/protocols/{pid}", headers=admin, json={**NEW_PROTOCOL, "name": "Chest Pain"})
    assert r.status_code == 409


def test_deactivated_protocol_disappears_for_nurses(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    pid = protocol_id(client, "Burns")
    client.patch(f"/admin/protocols/{pid}/active?active=false", headers=admin)
    names = [p["name"] for p in client.get("/protocols", headers=n1).json()]
    assert "Burns" not in names


def test_actions_are_audited(client):
    h = login(client, "nurse1@example.com")
    client.post("/auth/login", data={"username": "nurse1@example.com", "password": "bad-password"})
    c = start(client, h).json()
    answer_through(client, h, c["consultation_id"], c["step"], yes_orders={1})
    client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={"accept": True})
    with client.session() as db:
        actions = set(db.scalars(select(AuditLog.action)))
    assert {"login", "login_failed", "consultation_started", "consultation_closed"} <= actions
