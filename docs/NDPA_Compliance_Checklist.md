# NDPA 2023 Compliance Checklist

**System:** Nurse Telephone Triage Decision Support System (prototype, version 0.5)
**Law:** Nigeria Data Protection Act, 2023 (NDPA)
**Data processed:** caller age, caller sex, consent, a generated caller reference, triage answers, the disposition, any nurse override and its reason, and staff accounts.
**Classification:** the triage answers and dispositions are health information, which the NDPA treats as sensitive personal data. No caller names, phone numbers, or addresses are stored.

This checklist maps the main NDPA duties to how the software meets them and where the evidence is.
It covers the software only. Duties that rest with the organisation operating the service are listed in Part B.

---

## Part A: How the software meets each duty

| # | NDPA duty | How the system meets it | Evidence |
|---|---|---|---|
| 1 | **Lawful basis: consent** | Consent is recorded before triage starts. If the caller declines, the call ends and no consultation record is created. Only the fact that consent was declined is logged, with no caller details. | `app/routers/consultations.py` (start), consent step in `app/static/triage.html`; test `test_no_consent_stores_nothing` |
| 2 | **Transparency** | The nurse reads a short consent script that tells the caller what is collected and why. | Consent script in `app/static/triage.html` |
| 3 | **Purpose limitation** | Data is used only to triage the caller and to review the quality of triage. There are no analytics, marketing, or third-party integrations, and no data leaves the server. | Absence of any external integration; pages load nothing from the internet (test `test_pages_do_not_load_anything_from_the_internet`) |
| 4 | **Data minimisation** | Only age, sex, consent, a generated reference (for example C-000123), and triage answers are stored. No names, phone numbers, or addresses. The reference makes records pseudonymous. | `Consultation` table in `app/models.py` |
| 5 | **Accuracy** | Every request is checked by Pydantic. The database enforces valid values (age 0 to 120, sex, roles, levels). The decision engine always gives the same result for the same answers. The nurse can go back and correct an answer before saving. | `app/schemas.py`, constraints in `app/models.py`; tests `test_same_answers_always_give_same_result`, `test_back_undoes_last_answer` |
| 6 | **Storage limitation** | Records older than the retention period (`RETENTION_DAYS`, default 730 days) are deleted by a clean-up that runs as a dry run unless told otherwise. Each clean-up is logged. | `app/retention.py`, `scripts/retention.py`, `POST /admin/retention/purge`; tests `test_retention_deletes_only_old_records`, `test_retention_endpoint_defaults_to_dry_run` |
| 7 | **Confidentiality: access control** | Sign-in required for every page and endpoint. Passwords hashed with bcrypt. Tokens expire (`TOKEN_MINUTES`). Two roles: nurses see only their own consultations, administrators cannot answer triage questions. Deactivated users are refused at once. | `app/security.py`; tests `test_endpoints_need_login`, `test_nurse_cannot_use_admin_endpoints`, `test_nurse_sees_only_own_consultations_admin_sees_all`, `test_deactivated_user_cannot_log_in` |
| 8 | **Confidentiality: sign-in protection** | Accounts lock for 15 minutes after 5 failed sign-ins, including for unknown emails. Passwords need at least 8 characters with a letter and a number. | `app/routers/auth.py`; tests `test_account_locks_after_five_failed_attempts`, `test_unknown_email_is_also_rate_limited`, `test_password_policy` |
| 9 | **Confidentiality: unattended screens** | The interface signs the user out after 15 minutes without activity, with a one-minute warning. Sign-in is kept per browser tab and ends when the tab closes. | `IDLE_MINUTES` in `app/static/js/core.js` |
| 10 | **Security of processing** | Security headers on every response: Content Security Policy (no outside scripts, no framing), `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`. API responses are never cached (`Cache-Control: no-store`). HSTS is sent when served over HTTPS. The app refuses to start in production with a weak secret key. | `security_headers` in `app/main.py`, `app/config.py`; tests `test_security_headers_on_pages_and_api`, `test_api_responses_are_not_cached` |
| 11 | **Integrity of clinical content** | Every protocol passes a safety check before use: questions must run from most to least serious. A protocol already used in a consultation cannot be edited, so past records stay accurate. A closed consultation cannot be changed. | `app/protocols.py`; tests `test_unsafe_protocol_is_rejected_by_api`, `test_protocol_in_use_cannot_be_edited`, `test_closed_consultation_cannot_be_changed` |
| 12 | **Accountability** | The audit log records sign-ins, failed and blocked sign-ins, consultations started and saved, overrides with the original and new disposition, records opened by anyone other than the treating nurse, exports, erasures, retention clean-ups, and all user and protocol changes. Administrators can search it. | `app/audit.py`, `GET /admin/audit-logs`, `app/static/audit.html`; tests `test_actions_are_audited`, `test_admin_viewing_a_record_is_logged_but_own_nurse_is_not` |
| 13 | **Data subject right: access and portability** | An administrator can export a single consultation record as a JSON file. The export is logged. | `GET /admin/consultations/{id}/export`; test `test_admin_can_export_a_record` |
| 14 | **Data subject right: erasure** | An administrator can erase a consultation record after giving a reason and typing the caller reference to confirm. The audit log keeps only the reference, who erased it, and why. | `DELETE /admin/consultations/{id}`; test `test_erasure_needs_a_reason_and_removes_the_record` |
| 15 | **Rectification** | Answers can be corrected before the consultation is saved. Saved clinical records are not edited, to keep an accurate record of advice given. A wrong record can be erased with a reason and the call recorded again. | Back function; closed-record rule |
| 16 | **Breach detection support** | Failed and blocked sign-ins appear in the audit log and on its summary cards, which helps administrators spot attacks early. | `app/static/audit.html` |

---

## Part B: Duties for the organisation operating the service

The software supports these duties but cannot meet them on its own. They must be in place before the system is used with real patients.

| # | Duty | What is needed |
|---|---|---|
| 1 | Data protection officer | Appoint a data protection officer responsible for this service. |
| 2 | Registration | Check whether the organisation must register with the Nigeria Data Protection Commission, and register if so. |
| 3 | Data protection impact assessment | Carry out an impact assessment before live use, since the system processes health data. |
| 4 | Privacy notice | Publish a privacy notice explaining what is collected, why, how long it is kept, and how to make a request. |
| 5 | Retention period | Decide the retention period with the data protection officer and set `RETENTION_DAYS`. Schedule `python -m scripts.retention --delete` to run regularly. |
| 6 | Secure hosting | Serve the system only over HTTPS with a valid certificate. Encrypt the database disk and all backups. Restrict server and database access. Set `ENVIRONMENT=production` and a long random `SECRET_KEY`. |
| 7 | Processor agreements | Have a written agreement with any hosting or IT provider that processes the data. |
| 8 | Breach response | Keep a breach response plan, including notifying the Commission within 72 hours where the law requires it, and informing affected people where needed. |
| 9 | Staff training | Train nurses and administrators on confidentiality, consent, and the override process. |
| 10 | Clinical governance | Have qualified clinicians review and approve the protocols before live use, and review overrides regularly. |
| 11 | Handling requests | Set a process for verifying the identity of a caller who asks for access or erasure, using the caller reference given during the call. |

---

## Part C: Known limitations of the prototype

- The Content Security Policy allows inline scripts, because the interface uses them. It still blocks all scripts from other sites.
- Signing out on one device does not cancel tokens already issued; they expire after `TOKEN_MINUTES`.
- Encryption at rest depends on how the database server and disk are set up (Part B, item 6), not on the application.
- The audit log is kept indefinitely, so that accountability survives record deletion.
- The prototype has been tested with synthetic data only. No real patient data has been processed.
