# Nurse Telephone Triage Decision Support System

MIT Professional Master's Project, Miva Open University.
Sprint 1: database schema and protocol content.
Sprint 2: rule-based decision engine, scenario testing, and a console demo.
Sprint 3: FastAPI backend with login, roles, consultations, administration, and audit log.
Sprint 4: web interface for nurses and administrators.
Sprint 5: security hardening and NDPA 2023 compliance.
Sprint 6: testing and evaluation.

## What is in this sprint

- **8 database tables** matching the entity relationship diagram in Chapter Three (Figure 3.4).
- **10 symptom protocols** (78 triage questions) in `data/protocols/`, each with care advice for every result.
- **A safety check** that refuses any protocol where a less serious question comes before a more serious one (Section 3.5.5).
- **A seed script** that loads everything into PostgreSQL. It is safe to run more than once.
- **14 automated tests.**

> The protocols are a **draft for clinical review**. They are adapted from public WHO, NHS 111,
> and Nigerian guidance, and are not for use with real patients without review by qualified clinicians.

## Project structure

```
triage-dss/
  app/
    config.py        settings read from .env
    database.py      database connection
    main.py          the FastAPI application
    engine.py        the rule-based decision engine
    models.py        the 8 tables
    schemas.py       request and response shapes (checked by Pydantic)
    security.py      password hashing, login tokens, role checks
    audit.py         writes to the audit log
    retention.py     the data retention rule
    protocols.py     loads protocol files and checks the safety rules
    protocol_store.py saves protocols to the database
    routers/         API endpoints: auth, protocols, consultations, admin
    static/          the web interface (HTML, CSS, JavaScript, Inter font)
  data/protocols/    the 10 protocol files (JSON)
  data/scenarios.json 40 synthetic clinical scenarios with expected results
  migrations/        Alembic: creates the tables
  scripts/
    seed.py          loads dispositions and protocols into the database
    show_protocol.py prints protocols so you can check them
    run_scenarios.py runs the 40 scenarios and saves a results table
    triage_cli.py    interactive triage demo in the terminal
    create_user.py   creates nurse and admin accounts
    retention.py     deletes records older than the retention period
    evaluate.py      runs the full evaluation for Chapter Five
    sus_score.py     scores usability questionnaires
  tests/             automated tests
  docs/              NDPA checklist, usability kit, clinical review form
  results/           evaluation output (created by scripts.evaluate)
  requirements.txt
  .env.example
```

## Setup on Windows

Open **PowerShell** (or the terminal in VS Code) inside the `triage-dss` folder.

**1. Check Python (3.10 or newer)**
```powershell
python --version
```
If `python` is not recognised, use `py` instead of `python` in every command below.

**2. Create and activate a virtual environment**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If you see *"running scripts is disabled on this system"*, run this once, then try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
You will see `(.venv)` at the start of the line when it is active.

**3. Install the packages**
```powershell
pip install -r requirements.txt
```

**4. Create the database**

Easiest way: open **pgAdmin**, right-click **Databases**, then **Create > Database...**, and name it `triage_db`.

Or from PowerShell (change 16 to your PostgreSQL version if different):
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -c "CREATE DATABASE triage_db;"
```

**5. Add your database password**
```powershell
copy .env.example .env
notepad .env
```
Replace `YOUR_PASSWORD` with your PostgreSQL password and save.
If your password contains `@`, `:` or `/`, replace them with `%40`, `%3A` and `%2F`.

**6. Create the tables**
```powershell
alembic upgrade head
```

**7. Load the protocols**
```powershell
python -m scripts.seed
```
Expected output:
```
Dispositions ready: 4
Protocols added: 10, already present: 0
Triage questions in database: 78
```

**8. Check the protocols**
```powershell
python -m scripts.show_protocol
python -m scripts.show_protocol chest
```

**9. Run the tests**
```powershell
python -m pytest
```
Expected: `211 passed` (takes about a minute).

## Sprint 2: the decision engine

The engine (`app/engine.py`) walks through a protocol's questions from most to
least serious. The first "Yes" decides the result. If every answer is "No",
the result is self-care. It has no database code, so it can be tested on its own.

**Try a triage call in the terminal**
```powershell
python -m scripts.triage_cli
```
In Git Bash, if the questions do not appear, use `winpty python -m scripts.triage_cli`, or run it from PowerShell.

**Run the 40 clinical scenarios**
```powershell
python -m scripts.run_scenarios
```
This prints how many scenarios matched their expected result and saves
`results/scenario_results.csv`, which opens in Excel.

**What the tests check (160 in total)**
- Yes to each of the 78 questions returns that question's disposition and advice.
- No to every question returns self-care, for all 10 protocols.
- Questions are asked one at a time, in order. An unanswered earlier question is always asked first.
- The first Yes wins; later answers are ignored.
- Unsafe protocols are refused.
- The same answers always give the same result (1,000 repeats).
- The engine answers in well under 1 millisecond.
- All 40 clinical scenarios match their expected disposition.

## Sprint 3: the backend API

**1. Update packages and settings**
```powershell
pip install -r requirements.txt
```
Add these two lines to your `.env` file (see `.env.example`):
```
SECRET_KEY=paste-a-long-random-value-here
TOKEN_MINUTES=60
```
Make a random secret with:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

**2. Create your first accounts**
```powershell
python -m scripts.create_user --role admin --name "Your Name" --email you@example.com
python -m scripts.create_user --role nurse --name "Demo Nurse" --email nurse@example.com
```
You will be asked for each password. In Git Bash, put `winpty` in front if the prompt does not appear.

**3. Start the server**
```powershell
uvicorn app.main:app --reload --port 8081
```
Open **http://127.0.0.1:8081/docs** in your browser. This page lists every endpoint and lets you try them.

**4. Try a triage call on the docs page**
1. Click **Authorize** (top right). Type the nurse email in *username* and the password, then click Authorize.
2. `GET /protocols`: note a `protocol_id`.
3. `POST /consultations`: send age, sex, `consent_given: true`, and the `protocol_id`. The reply contains the first question.
4. `POST /consultations/{id}/answers`: send the `question_id` and `true` or `false`. Repeat until `"done": true`.
5. `POST /consultations/{id}/finalize`: send `{"accept": true}`.

Press **Ctrl+C** in the terminal to stop the server.

**Endpoints (matches Table 3.6 in the report)**

| Method | Endpoint | Purpose | Role |
|---|---|---|---|
| POST | /auth/login | Log in and receive a token | All |
| GET | /auth/me | Current user | All |
| GET | /protocols | List active protocols | Nurse, Admin |
| GET | /protocols/{id} | One protocol with questions and advice | Nurse, Admin |
| POST | /consultations | Start a consultation (consent required) | Nurse |
| POST | /consultations/{id}/answers | Answer the current question, get the next step | Nurse |
| DELETE | /consultations/{id}/answers/last | Go back one question | Nurse |
| POST | /consultations/{id}/finalize | Accept, or override with a reason | Nurse |
| GET | /consultations | List consultations (nurses see their own) | Nurse, Admin |
| GET | /consultations/{id} | One consultation in full | Nurse, Admin |
| GET, POST | /admin/users | List or create users | Admin |
| PATCH | /admin/users/{id} | Update, deactivate, or reset password | Admin |
| GET, POST | /admin/protocols | List all or create a protocol (safety-checked) | Admin |
| PUT | /admin/protocols/{id} | Edit a protocol not yet used in a consultation | Admin |
| PATCH | /admin/protocols/{id}/active | Activate or deactivate | Admin |
| GET | /admin/audit-logs | View the audit log | Admin |

**Rules the API enforces**
- No consent, no record: the call ends and nothing is stored.
- Questions must be answered in order; skipping is refused.
- A result cannot be saved until the questions reach one.
- An override must include a reason.
- A closed consultation cannot be changed.
- Nurses only see their own consultations. Admins cannot answer triage questions.
- A protocol used in a consultation cannot be edited; save a new version instead.
- Logins, failed logins, consultations, overrides, and admin changes are all written to the audit log.

## Sprint 4: the web interface

Start the server, then open **http://127.0.0.1:8081** and sign in.
```powershell
uvicorn app.main:app --reload --port 8081
```

**Nurse screens**
- **New consultation:** caller age, sex, and consent, then the protocol for the main symptom.
- **Triage questions:** one question at a time, most serious first. Press **Y** for Yes, **N** for No, **Backspace** to go back.
- **Result:** colour-coded disposition, the reason for it, and the care advice to read out. Accept, or override with a reason, then save.
- **Consultations:** your past calls, with search and filters. Open any call for the full record. Unfinished calls can be continued.
- **Protocols:** read-only reference copy of every active protocol.

**Administrator screens**
- **Consultations:** every nurse's calls, with summary counts.
- **Protocols:** switch protocols on or off, and import a new one. Imports go through the safety check and are refused if a less serious question comes before a more serious one.
- **Users:** add nurses and administrators, edit roles, deactivate accounts, reset passwords.
- **Audit log:** every sign-in, consultation, override, and change, with search and filters.

The interface is plain HTML, CSS, and JavaScript with no external downloads, so it works without internet.
Times are shown in West Africa Time (Lagos). Signing in lasts until the token expires or the browser tab is closed.

## Sprint 5: security and data protection

**New settings** (add to `.env`; defaults shown, see `.env.example`):
```
ENVIRONMENT=development
LOGIN_MAX_ATTEMPTS=5
LOGIN_LOCK_MINUTES=15
RETENTION_DAYS=730
```

**What was added**
- **Account lock:** 5 failed sign-ins lock the account for 15 minutes. A warning shows when 2 attempts are left.
- **Password policy:** at least 8 characters with a letter and a number.
- **Security headers:** Content Security Policy, no framing, no content sniffing, no referrer, and API responses are never cached.
- **Idle sign-out:** after 15 minutes without activity, with a warning one minute before.
- **Access logging:** when anyone other than the treating nurse opens a record, it is logged.
- **Export and erase (admin):** on a consultation record, *Export* downloads it as JSON and *Erase* deletes it after a reason and confirmation. Both are logged.
- **Data retention:**
  ```powershell
  python -m scripts.retention            # dry run: shows what would be deleted
  python -m scripts.retention --delete   # deletes records older than RETENTION_DAYS
  ```
- **Startup check:** a warning if `SECRET_KEY` is the default; with `ENVIRONMENT=production` the server refuses to start.

The full mapping of NDPA duties to code and tests is in **`docs/NDPA_Compliance_Checklist.md`**.

## Sprint 6: testing and evaluation

**Run the full evaluation** (install the coverage tool once with `pip install -r requirements.txt`):
```powershell
python -m scripts.evaluate
```
It runs every test with code coverage, the 40 clinical scenarios, and timing checks, then writes to `results/`:

| File | Contents |
|---|---|
| `evaluation_report.md` | Summary tables for Chapter Five, including the objectives check |
| `test_summary.csv` | Tests by category |
| `scenario_results.csv` | All 40 scenarios, expected against system result |
| `confusion_matrix.csv` | Expected disposition against system disposition |
| `performance.csv` | Engine and API timings |
| `coverage.json` | Code coverage by file |

**Usability testing with nurses:** follow `docs/Usability_Evaluation_Kit.md` (5 tasks and the SUS questionnaire),
enter the answers in `data/sus_responses.csv`, then run `python -m scripts.sus_score`.

**Clinical review:** give `docs/Clinical_Review_Form.md` to a qualified nurse or doctor to review every protocol question.

## Changing a protocol

1. Edit the JSON file in `data/protocols/`.
2. Raise its `"version"` (for example `"1.0"` to `"1.1"`).
3. Run `python -m pytest` to check the safety rules still pass.
4. Run `python -m scripts.seed` to load the new version.

## Common problems

| Problem | Fix |
|---|---|
| `password authentication failed` | The password in `.env` is wrong. |
| `database "triage_db" does not exist` | Do step 4. |
| `connection refused` | PostgreSQL is not running. Open **Services**, find *postgresql-x64-16*, and click **Start**. |
| `No module named app` | Run commands from inside the `triage-dss` folder. |
| `alembic` not recognised | The virtual environment is not active. Repeat step 2. |
| `Too many failed sign-in attempts` | Wait 15 minutes, or ask an admin to reset your password. |
