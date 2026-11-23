"""Score System Usability Scale (SUS) answers and task results.

    python -m scripts.sus_score                       # reads data/sus_responses.csv
    python -m scripts.sus_score path/to/answers.csv

The CSV needs columns q1..q10 (1 to 5). Optional columns t1..t5 hold Y or N for task completion.
"""
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sus_score(answers: list[int]) -> float:
    """Standard SUS scoring: odd items score-1, even items 5-score, total times 2.5."""
    if len(answers) != 10 or any(a not in (1, 2, 3, 4, 5) for a in answers):
        raise ValueError("SUS needs 10 answers, each from 1 to 5.")
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))
    return total * 2.5


def rating(score: float) -> str:
    if score >= 80.3:
        return "Excellent"
    if score >= 68:
        return "Good (above average)"
    if score >= 51:
        return "OK (below average)"
    return "Poor"


def summarise(path: Path) -> dict:
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    rows = [r for r in rows if (r.get("q1") or "").strip()]
    scores = [(r["participant"], sus_score([int(r[f"q{i}"]) for i in range(1, 11)])) for r in rows]
    tasks = {}
    for t in [f"t{i}" for i in range(1, 6)]:
        done = [r[t].strip().upper() for r in rows if (r.get(t) or "").strip()]
        if done:
            tasks[t.upper()] = (done.count("Y"), len(done))
    return {"scores": scores, "tasks": tasks}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "sus_responses.csv"
    s = summarise(path)
    if not s["scores"]:
        print(f"No responses yet in {path}. Add one row per participant, then run this again.")
        return
    values = [v for _, v in s["scores"]]
    print(f"Participants: {len(values)}")
    for p, v in s["scores"]:
        print(f"  {p:<6} {v:5.1f}  {rating(v)}")
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    print(f"\nMean SUS score: {mean:.1f} (SD {sd:.1f}, range {min(values):.1f} to {max(values):.1f}): {rating(mean)}")
    if s["tasks"]:
        print("\nTask completion:")
        for t, (ok, n) in s["tasks"].items():
            print(f"  {t}: {ok}/{n} ({100 * ok / n:.0f}%)")


if __name__ == "__main__":
    main()
