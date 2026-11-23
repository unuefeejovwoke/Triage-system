"""Security and data protection tests (Sprint 5)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import AuditLog, Consultation
from app.retention import purge_old_consultations
from app.security import password_problem
from tests.test_api import answer_through, client, login, start  # noqa: F401  (client is a fixture)

PASSWORD = "Password123"


def actions(client):
    with client.session() as db:
        return [a for a in db.scalars(select(AuditLog.action).order_by(AuditLog.log_id))]


# ---------------------------------------------------------------- sign-in protection

def test_account_locks_after_five_failed_attempts(client):
    for _ in range(5):
        r = client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-pass1"})
        assert r.status_code == 401
    r = client.post("/auth/login", data={"username": "nurse1@example.com", "password": PASSWORD})
    assert r.status_code == 429 and "Too many failed" in r.json()["detail"]
    assert "login_locked" in actions(client)


def test_warning_before_lock(client):
    for _ in range(3):
        r = client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-pass1"})
    assert "2 attempts left" in r.json()["detail"]


def test_lock_does_not_affect_other_users(client):
    for _ in range(5):
        client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-pass1"})
    login(client, "nurse2@example.com")


def test_successful_login_resets_the_count(client):
    for _ in range(4):
        client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-pass1"})
    login(client, "nurse1@example.com")
    for _ in range(4):
        client.post("/auth/login", data={"username": "nurse1@example.com", "password": "wrong-pass1"})
    login(client, "nurse1@example.com")


def test_unknown_email_is_also_rate_limited(client):
    for _ in range(5):
        client.post("/auth/login", data={"username": "nobody@example.com", "password": "guess12345"})
    r = client.post("/auth/login", data={"username": "nobody@example.com", "password": "guess12345"})
    assert r.status_code == 429


# ---------------------------------------------------------------- password policy

def test_password_policy():
    assert password_problem("short1") is not None
    assert password_problem("onlyletters") is not None
    assert password_problem("1234567890") is not None
    assert password_problem("GoodPass123") is None


def test_weak_password_is_rejected_by_api(client):
    admin = login(client, "admin@example.com")
    r = client.post("/admin/users", headers=admin, json={
        "full_name": "Weak", "email": "weak@example.com", "password": "allletters", "role": "nurse"})
    assert r.status_code == 422 and "letter and one number" in r.text
    me = client.get("/auth/me", headers=admin).json()
    r = client.patch(f"/admin/users/{me['user_id']}", headers=admin, json={"password": "short"})
    assert r.status_code == 422


# ---------------------------------------------------------------- headers

def test_security_headers_on_pages_and_api(client):
    for path in ["/ui/login.html", "/health"]:
        h = client.get(path).headers
        assert h["X-Content-Type-Options"] == "nosniff"
        assert h["X-Frame-Options"] == "DENY"
        assert h["Referrer-Policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
        assert "default-src 'self'" in h["Content-Security-Policy"]


def test_api_responses_are_not_cached(client):
    h = login(client, "nurse1@example.com")
    assert client.get("/protocols", headers=h).headers["Cache-Control"] == "no-store"


def test_docs_page_still_works(client):
    r = client.get("/docs")
    assert r.status_code == 200 and "Content-Security-Policy" not in r.headers


# ---------------------------------------------------------------- access logging, export, erasure

def test_admin_viewing_a_record_is_logged_but_own_nurse_is_not(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    c = start(client, n1).json()
    client.get(f"/consultations/{c['consultation_id']}", headers=n1)
    assert "consultation_viewed" not in actions(client)
    client.get(f"/consultations/{c['consultation_id']}", headers=admin)
    assert "consultation_viewed" in actions(client)


def test_admin_can_export_a_record(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    c = start(client, n1).json()
    answer_through(client, n1, c["consultation_id"], c["step"], yes_orders={1})
    r = client.get(f"/admin/consultations/{c['consultation_id']}/export", headers=admin)
    assert r.status_code == 200 and "attachment" in r.headers["Content-Disposition"]
    assert r.json()["caller_ref"] == c["caller_ref"] and len(r.json()["answers"]) == 1
    assert "consultation_exported" in actions(client)
    assert client.get(f"/admin/consultations/{c['consultation_id']}/export", headers=n1).status_code == 403


def test_erasure_needs_a_reason_and_removes_the_record(client):
    n1, admin = login(client, "nurse1@example.com"), login(client, "admin@example.com")
    c = start(client, n1).json()
    cid = c["consultation_id"]
    assert client.delete(f"/admin/consultations/{cid}", headers=admin).status_code == 422
    assert client.delete(f"/admin/consultations/{cid}?reason=Caller%20asked%20for%20erasure", headers=n1).status_code == 403
    r = client.delete(f"/admin/consultations/{cid}?reason=Caller%20asked%20for%20erasure", headers=admin)
    assert r.status_code == 204
    assert client.get(f"/consultations/{cid}", headers=admin).status_code == 404
    with client.session() as db:
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "consultation_erased"))
    assert entry.entity.startswith(c["caller_ref"])


# ---------------------------------------------------------------- retention

def test_retention_deletes_only_old_records(client):
    n1 = login(client, "nurse1@example.com")
    old, new = start(client, n1).json(), start(client, n1).json()
    with client.session() as db:
        o = db.get(Consultation, old["consultation_id"])
        o.started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=800)
        o.ended_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=800)
        db.commit()
        dry = purge_old_consultations(db, dry_run=True, days=730)
        assert dry["matched"] == 1 and dry["deleted"] == 0
        assert db.get(Consultation, old["consultation_id"]) is not None
        done = purge_old_consultations(db, dry_run=False, days=730)
        assert done["deleted"] == 1
        assert db.get(Consultation, old["consultation_id"]) is None
        assert db.get(Consultation, new["consultation_id"]) is not None
    assert "retention_purge" in actions(client)


def test_retention_endpoint_defaults_to_dry_run(client):
    admin = login(client, "admin@example.com")
    r = client.post("/admin/retention/purge", headers=admin).json()
    assert r["dry_run"] is True and r["deleted"] == 0
