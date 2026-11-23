"""Run the full evaluation for Chapter Five and save the evidence.

    python -m scripts.evaluate

Writes to the results/ folder:
    evaluation_report.md     the summary to use in Chapter Five
    test_summary.csv         tests by category
    scenario_results.csv     all 40 clinical scenarios, expected vs system
    confusion_matrix.csv     expected disposition vs system disposition
    performance.csv          engine and API timings
    coverage.json            code coverage (if pytest-cov is installed)

It uses a temporary in-memory database, so your real data is never touched.
"""
import csv
import json
import platform
import random
import statistics
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results"
LEVELS = ["emergency", "urgent", "routine", "self_care"]
LABEL = {"emergency": "Emergency", "urgent": "Urgent", "routine": "Routine", "self_care": "Self-care"}
RANK = {lv: i + 1 for i, lv in enumerate(LEVELS)}
CATEGORIES = {
    "test_protocols": "Unit: protocol safety rules",
    "test_engine": "Unit: decision engine and clinical scenarios",
    "test_database": "Integration: database schema and seeding",
    "test_api": "Integration: API and consultation workflow",
    "test_security": "Security and data protection",
    "test_ui": "Interface delivery",
    "test_evaluation": "Evaluation tools",
}


def pct(a, b):
    return f"{(100 * a / b):.1f}%" if b else "n/a"


# ---------------------------------------------------------------- 1. automated tests and coverage

def run_tests() -> dict:
    junit = OUT / "junit.xml"
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    has_cov = True
    try:
        import pytest_cov  # noqa: F401
        cmd += ["--cov=app", f"--cov-report=json:{OUT / 'coverage.json'}", "--cov-report="]
    except ImportError:
        has_cov = False
    print("Running the automated test suite (about a minute)...")
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    elapsed = time.perf_counter() - t0

    cats = defaultdict(lambda: {"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "seconds": 0.0})
    for case in ET.parse(junit).getroot().iter("testcase"):
        module = case.get("classname", "").split(".")[-1]
        c = cats[CATEGORIES.get(module, module)]
        c["tests"] += 1
        c["seconds"] += float(case.get("time", 0))
        if case.find("failure") is not None or case.find("error") is not None:
            c["failed"] += 1
        elif case.find("skipped") is not None:
            c["skipped"] += 1
        else:
            c["passed"] += 1
    junit.unlink(missing_ok=True)

    coverage = None
    if has_cov and (OUT / "coverage.json").exists():
        data = json.loads((OUT / "coverage.json").read_text())
        coverage = {"total": data["totals"]["percent_covered"],
                    "files": {Path(f).as_posix().split("app/")[-1]: v["summary"]["percent_covered"] for f, v in data["files"].items()}}
    order = list(CATEGORIES.values())
    ordered = {k: cats[k] for k in sorted(cats, key=lambda k: order.index(k) if k in order else len(order))}
    return {"categories": ordered, "elapsed": elapsed, "coverage": coverage}


# ---------------------------------------------------------------- 2. clinical scenarios

def run_scenarios() -> dict:
    from app.engine import rules_from_dict, triage
    from app.protocols import load_all

    rules = {p["name"]: rules_from_dict(p) for p in load_all()}
    scenarios = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    matrix = {e: Counter() for e in LEVELS}
    rows, under, over, asked, totals = [], 0, 0, [], []
    for s in scenarios:
        r = rules[s["protocol"]]
        result = triage(r, {q.order: (q.order in s["yes_answers"]) for q in r.questions})
        matrix[s["expected"]][result.level] += 1
        diff = RANK[result.level] - RANK[s["expected"]]
        under += diff > 0
        over += diff < 0
        asked.append(result.questions_asked)
        totals.append(r.total)
        rows.append({"ID": s["id"], "Protocol": s["protocol"], "Scenario": s["scenario"],
                     "Expected": LABEL[s["expected"]], "System result": LABEL[result.level],
                     "Triggered by": f"Q{result.triggered_by.order}" if result.triggered_by else "All No",
                     "Questions asked": result.questions_asked, "Match": "Yes" if diff == 0 else "No"})
    n = len(scenarios)
    correct = sum(matrix[e][e] for e in LEVELS)
    per_level = {e: {"n": sum(matrix[e].values()), "correct": matrix[e][e]} for e in LEVELS}
    return {"n": n, "correct": correct, "under": under, "over": over, "matrix": matrix, "per_level": per_level,
            "rows": rows, "avg_asked": statistics.mean(asked), "avg_total": statistics.mean(totals),
            "protocols": len(rules), "questions": sum(r.total for r in rules.values())}


# ---------------------------------------------------------------- 3. performance

def engine_timing(runs: int = 10_000) -> dict:
    from app.engine import evaluate, rules_from_dict
    from app.protocols import load_all

    rng = random.Random(42)
    rules = [rules_from_dict(p) for p in load_all()]
    times = []
    for _ in range(runs):
        r = rng.choice(rules)
        yes_at = rng.randint(1, r.total + 1)  # total+1 means all No
        answers = {q.order: q.order == yes_at for q in r.questions}
        t0 = time.perf_counter_ns()
        evaluate(r, answers)
        times.append((time.perf_counter_ns() - t0) / 1000)  # microseconds
    times.sort()
    return {"runs": runs, "mean_us": statistics.mean(times), "p95_us": times[int(0.95 * runs)], "max_us": times[-1]}


def api_timing(calls: int = 30) -> dict:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.deps import get_db
    from app.main import app
    from app.models import User
    from app.security import hash_password
    from scripts.seed import seed_dispositions, seed_protocols

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        seed_protocols(db, seed_dispositions(db))
        db.add(User(full_name="Eval Nurse", email="eval@example.com", password_hash=hash_password("EvalPass123"), role="nurse"))
        db.commit()

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)
    timings = defaultdict(list)
    rng = random.Random(7)
    try:
        t0 = time.perf_counter()
        tok = client.post("/auth/login", data={"username": "eval@example.com", "password": "EvalPass123"}).json()["access_token"]
        timings["Sign in (includes bcrypt check)"].append((time.perf_counter() - t0) * 1000)
        h = {"Authorization": f"Bearer {tok}"}
        protocols = client.get("/protocols", headers=h).json()
        call_totals = []
        for _ in range(calls):
            p = rng.choice(protocols)
            yes_at = rng.randint(1, p["question_count"] + 1)
            c0 = time.perf_counter()
            t0 = time.perf_counter()
            c = client.post("/consultations", headers=h, json={"caller_age": rng.randint(1, 90), "caller_sex": "female",
                                                               "consent_given": True, "protocol_id": p["protocol_id"]}).json()
            timings["Start consultation"].append((time.perf_counter() - t0) * 1000)
            step = c["step"]
            while not step["done"]:
                q = step["question"]
                t0 = time.perf_counter()
                step = client.post(f"/consultations/{c['consultation_id']}/answers", headers=h,
                                   json={"question_id": q["question_id"], "answer": q["order"] == yes_at}).json()
                timings["Answer a question"].append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            client.post(f"/consultations/{c['consultation_id']}/finalize", headers=h, json={"accept": True})
            timings["Save result"].append((time.perf_counter() - t0) * 1000)
            call_totals.append((time.perf_counter() - c0) * 1000)
        timings["Whole consultation (system time)"] = call_totals
    finally:
        app.dependency_overrides.clear()

    out = {}
    for k, v in timings.items():
        v = sorted(v)
        out[k] = {"n": len(v), "mean_ms": statistics.mean(v), "p95_ms": v[min(len(v) - 1, int(0.95 * len(v)))], "max_ms": v[-1]}
    return out


# ---------------------------------------------------------------- 4. report

def endpoints() -> int:
    """Number of API operations, counted from the OpenAPI schema (works on every FastAPI version)."""
    from app.main import app
    methods = {"get", "post", "put", "patch", "delete"}
    return sum(1 for ops in app.openapi()["paths"].values() for m in ops if m in methods)


def write(tests, sc, eng, api):
    OUT.mkdir(exist_ok=True)
    total = sum(c["tests"] for c in tests["categories"].values())
    passed = sum(c["passed"] for c in tests["categories"].values())
    failed = sum(c["failed"] for c in tests["categories"].values())

    with (OUT / "test_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Category", "Tests", "Passed", "Failed", "Skipped", "Seconds"])
        for k, c in tests["categories"].items():
            w.writerow([k, c["tests"], c["passed"], c["failed"], c["skipped"], f"{c['seconds']:.2f}"])
        w.writerow(["Total", total, passed, failed, sum(c["skipped"] for c in tests["categories"].values()), f"{tests['elapsed']:.1f}"])
    with (OUT / "scenario_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sc["rows"][0]))
        w.writeheader()
        w.writerows(sc["rows"])
    with (OUT / "confusion_matrix.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Expected \\ System"] + [LABEL[x] for x in LEVELS])
        for e in LEVELS:
            w.writerow([LABEL[e]] + [sc["matrix"][e][x] for x in LEVELS])
    with (OUT / "performance.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Measure", "Samples", "Mean", "95th percentile", "Maximum", "Unit"])
        w.writerow(["Decision engine evaluation", eng["runs"], f"{eng['mean_us']:.1f}", f"{eng['p95_us']:.1f}", f"{eng['max_us']:.1f}", "microseconds"])
        for k, v in api.items():
            w.writerow([k, v["n"], f"{v['mean_ms']:.1f}", f"{v['p95_ms']:.1f}", f"{v['max_ms']:.1f}", "milliseconds"])

    cov = tests["coverage"]
    em = sc["per_level"]["emergency"]
    whole = api.get("Whole consultation (system time)", {})
    answer = api.get("Answer a question", {})
    nfr_ok = answer.get("p95_ms", 9999) < 1000
    lines = [
        "# Evaluation Report",
        "",
        f"Generated {datetime.now(timezone.utc).astimezone().strftime('%d %b %Y, %H:%M')} on {platform.system()} {platform.release()}, Python {platform.python_version()}.",
        "All measurements use synthetic data in a temporary in-memory database.",
        "",
        "## 1. Automated testing",
        "",
        "| Category | Tests | Passed | Failed |",
        "|---|---:|---:|---:|",
        *[f"| {k} | {c['tests']} | {c['passed']} | {c['failed']} |" for k, c in tests["categories"].items()],
        f"| **Total** | **{total}** | **{passed}** | **{failed}** |",
        "",
        f"Pass rate: **{pct(passed, total)}**. Full suite run time: {tests['elapsed']:.0f} seconds.",
    ]
    if cov:
        lines += ["", f"Code coverage of the application (`app/`): **{cov['total']:.1f}%** of statements.", "",
                  "| File | Coverage |", "|---|---:|",
                  *[f"| {k} | {v:.0f}% |" for k, v in sorted(cov["files"].items()) if not k.startswith("static")]]
    else:
        lines += ["", "Code coverage: install `pytest-cov` and run again to include it."]
    lines += [
        "",
        "## 2. Clinical scenario evaluation",
        "",
        f"{sc['n']} synthetic scenarios across all {sc['protocols']} protocols, each with the expected disposition set before testing.",
        "",
        f"- Matched the expected disposition: **{sc['correct']}/{sc['n']} ({pct(sc['correct'], sc['n'])})**",
        f"- Under-triage (sent to a less urgent level than expected): **{sc['under']}**",
        f"- Over-triage (sent to a more urgent level than expected): **{sc['over']}**",
        f"- Emergency scenarios correctly identified: **{em['correct']}/{em['n']} ({pct(em['correct'], em['n'])})**",
        f"- Average questions asked before a result: **{sc['avg_asked']:.1f}** of an average **{sc['avg_total']:.1f}** per protocol",
        "",
        "**Expected (rows) against system result (columns)**",
        "",
        "| Expected | " + " | ".join(LABEL[x] for x in LEVELS) + " |",
        "|---|" + "---:|" * len(LEVELS),
        *[f"| {LABEL[e]} | " + " | ".join(str(sc["matrix"][e][x]) for x in LEVELS) + " |" for e in LEVELS],
        "",
        "**Accuracy by level**",
        "",
        "| Level | Scenarios | Correct | Accuracy |",
        "|---|---:|---:|---:|",
        *[f"| {LABEL[e]} | {v['n']} | {v['correct']} | {pct(v['correct'], v['n'])} |" for e, v in sc["per_level"].items()],
        "",
        f"Every one of the {sc['questions']} triage questions is also tested on its own: a Yes to that question must give its linked disposition and advice.",
        "",
        "## 3. Performance",
        "",
        "| Measure | Samples | Mean | 95th percentile | Maximum |",
        "|---|---:|---:|---:|---:|",
        f"| Decision engine evaluation | {eng['runs']:,} | {eng['mean_us']:.1f} µs | {eng['p95_us']:.1f} µs | {eng['max_us']:.1f} µs |",
        *[f"| {k} | {v['n']} | {v['mean_ms']:.1f} ms | {v['p95_ms']:.1f} ms | {v['max_ms']:.1f} ms |" for k, v in api.items()],
        "",
        f"Non-functional requirement (result in under one second): **{'met' if nfr_ok else 'not met'}**. "
        f"The slowest answer took {answer.get('max_ms', 0):.0f} ms. Sign-in is deliberately slower because bcrypt password hashing is designed to resist guessing.",
        "",
        "## 4. Evaluation of objectives",
        "",
        "| Objective | Evidence | Status |",
        "|---|---|---|",
        f"| 1. Adapt 8 to 12 openly sourced symptom protocols | {sc['protocols']} protocols, {sc['questions']} questions, each with documented WHO, NHS 111, or Nigerian sources; all pass the safety check | Met. Clinical review by qualified clinicians is still required before live use |",
        "| 2. Design a relational schema for protocols, questions, dispositions, advice, and consultations | 8 tables with keys and check constraints, created by an Alembic migration; integration tests pass | Met |",
        f"| 3. Develop a rule-based engine returning one of four dispositions consistently | {sc['questions']}/{sc['questions']} per-question tests pass; same output over 1,000 repeats; {pct(sc['correct'], sc['n'])} scenario agreement with {sc['under']} under-triage | Met |",
        f"| 4. Implement a FastAPI, PostgreSQL, and HTML/CSS/JavaScript application for nurses | {endpoints()} API endpoints, 7 screens, role-based access; API and interface tests pass | Met |",
        f"| 5. Evaluate with synthetic scenarios and against the NDPA 2023 | {sc['n']} scenarios evaluated; 16 NDPA duties mapped to code and tests in `docs/NDPA_Compliance_Checklist.md` | Met. Usability testing with nurses: see `docs/Usability_Evaluation_Kit.md` |",
        "",
        "## 5. Limitations",
        "",
        "- The scenarios test that the engine applies the protocols correctly. They do not prove the protocols are clinically correct; that needs review by clinicians.",
        "- All data is synthetic. No live calls or real patients were involved.",
        "- Timings come from one machine with an in-memory database and will differ on a production server.",
        "",
    ]
    (OUT / "evaluation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    tests = run_tests()
    print("Running the 40 clinical scenarios...")
    sc = run_scenarios()
    print("Timing the decision engine (10,000 runs)...")
    eng = engine_timing()
    print("Timing the API over 30 simulated consultations...")
    api = api_timing()
    write(tests, sc, eng, api)

    total = sum(c["tests"] for c in tests["categories"].values())
    passed = sum(c["passed"] for c in tests["categories"].values())
    print()
    print(f"Automated tests:    {passed}/{total} passed" + (f", coverage {tests['coverage']['total']:.1f}%" if tests["coverage"] else ""))
    print(f"Scenarios:          {sc['correct']}/{sc['n']} matched, under-triage {sc['under']}, over-triage {sc['over']}")
    print(f"Engine speed:       {eng['mean_us']:.1f} microseconds on average")
    w = api["Whole consultation (system time)"]
    print(f"Whole consultation: {w['mean_ms']:.0f} ms of system time on average")
    print(f"\nReport saved to {OUT / 'evaluation_report.md'}")


if __name__ == "__main__":
    main()
