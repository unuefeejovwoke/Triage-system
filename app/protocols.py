"""Load protocol files and check that they are safe to use.

Each protocol is a JSON file in data/protocols/. The rules checked here are the
ones described in Chapter Three (Section 3.5.5):

1. Questions are numbered 1, 2, 3, ... with no gaps or repeats.
2. Questions are ordered from most to least serious. A question can never
   point to a less serious disposition than a question that comes after it,
   otherwise a caller could be sent home before being asked about a danger sign.
3. No question points to self-care. Self-care is only the result when every
   answer is "No".
4. Care advice exists for every disposition the protocol can return,
   including self-care.
"""
import json
from dataclasses import dataclass
from pathlib import Path

PROTOCOL_DIR = Path(__file__).resolve().parent.parent / "data" / "protocols"

SEVERITY = {"emergency": 1, "urgent": 2, "routine": 3, "self_care": 4}

DISPOSITIONS = [
    ("emergency", 1, "Life-threatening signs present. Call 112 or go to the nearest emergency department now."),
    ("urgent", 2, "Needs to be seen by a clinician within hours. Go to a hospital or clinic today."),
    ("routine", 3, "Needs a clinician, but not urgently. Book a clinic appointment within the next few days."),
    ("self_care", 4, "Safe to manage at home with care advice. Call back if symptoms get worse."),
]


@dataclass
class ProtocolError(Exception):
    file: str
    problems: list[str]

    def __str__(self) -> str:
        return f"{self.file}:\n  - " + "\n  - ".join(self.problems)


def validate(data: dict, file: str = "<protocol>") -> None:
    """Raise ProtocolError if the protocol breaks any safety rule."""
    problems: list[str] = []

    for key in ("name", "version", "population", "source_guidance", "questions", "advice"):
        if key not in data:
            problems.append(f"missing field '{key}'")
    if problems:
        raise ProtocolError(file, problems)

    questions = data["questions"]
    if not questions:
        problems.append("protocol has no questions")

    orders = [q.get("order") for q in questions]
    if orders != list(range(1, len(questions) + 1)):
        problems.append(f"question order must be 1..{len(questions)} with no gaps, got {orders}")

    previous_rank = 1
    for q in questions:
        level = q.get("disposition")
        text = (q.get("text") or "").strip()
        if not text:
            problems.append(f"question {q.get('order')} has no text")
        if level not in SEVERITY:
            problems.append(f"question {q.get('order')} has unknown disposition '{level}'")
            continue
        if level == "self_care":
            problems.append(f"question {q.get('order')} points to self_care; self-care is only the default result")
        rank = SEVERITY[level]
        if rank < previous_rank:
            problems.append(
                f"question {q.get('order')} ({level}) comes after a less serious question; "
                "move it higher so danger signs are asked first"
            )
        previous_rank = max(previous_rank, rank)

    used = {q.get("disposition") for q in questions if q.get("disposition") in SEVERITY} | {"self_care"}
    advice = data["advice"]
    for level in sorted(used, key=SEVERITY.get):
        lines = advice.get(level)
        if not lines or not all(isinstance(x, str) and x.strip() for x in lines):
            problems.append(f"missing care advice for '{level}'")
    for level in advice:
        if level not in SEVERITY:
            problems.append(f"advice given for unknown disposition '{level}'")

    if problems:
        raise ProtocolError(file, problems)


def load_all(directory: Path = PROTOCOL_DIR) -> list[dict]:
    """Load and validate every protocol file. Stops with a clear error if any file is unsafe."""
    protocols = []
    errors = []
    for path in sorted(directory.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        try:
            validate(data, path.name)
            protocols.append(data)
        except ProtocolError as e:
            errors.append(str(e))
    if errors:
        raise SystemExit("Protocol check failed:\n" + "\n".join(errors))
    return protocols
