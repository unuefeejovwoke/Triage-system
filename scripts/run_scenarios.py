"""Run the 40 clinical scenarios through the engine and save the results.

    python -m scripts.run_scenarios

Prints a summary and writes results/scenario_results.csv, which you can open
in Excel and use as evidence in Chapter Five.
"""
import csv
import json
from collections import Counter
from pathlib import Path

from app.engine import triage, rules_from_dict
from app.protocols import load_all

ROOT = Path(__file__).resolve().parent.parent
LABEL = {"emergency": "Emergency", "urgent": "Urgent", "routine": "Routine", "self_care": "Self-care"}


def main() -> None:
    rules = {p["name"]: rules_from_dict(p) for p in load_all()}
    scenarios = json.loads((ROOT / "data" / "scenarios.json").read_text(encoding="utf-8"))
    rows, passed = [], 0
    by_level = Counter()
    for s in scenarios:
        r = rules[s["protocol"]]
        answers = {q.order: (q.order in s["yes_answers"]) for q in r.questions}
        result = triage(r, answers)
        ok = result.level == s["expected"]
        passed += ok
        by_level[(s["expected"], ok)] += 1
        rows.append({
            "ID": s["id"], "Protocol": s["protocol"], "Scenario": s["scenario"],
            "Expected": LABEL[s["expected"]], "System result": LABEL[result.level],
            "Triggered by": f"Q{result.triggered_by.order}" if result.triggered_by else "All No",
            "Questions asked": result.questions_asked, "Match": "Yes" if ok else "NO",
        })
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with (out / "scenario_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    total = len(scenarios)
    print(f"Scenarios run: {total}")
    print(f"Matched expected disposition: {passed}/{total} ({passed / total:.0%})\n")
    print(f"{'Expected level':<16}{'Scenarios':>10}{'Matched':>10}")
    for level in LABEL:
        n = by_level[(level, True)] + by_level[(level, False)]
        print(f"{LABEL[level]:<16}{n:>10}{by_level[(level, True)]:>10}")
    misses = [r for r in rows if r["Match"] == "NO"]
    if misses:
        print("\nMismatches:")
        for r in misses:
            print(f"  {r['ID']} {r['Protocol']}: expected {r['Expected']}, got {r['System result']}")
    print(f"\nFull table saved to {out / 'scenario_results.csv'}")


if __name__ == "__main__":
    main()
