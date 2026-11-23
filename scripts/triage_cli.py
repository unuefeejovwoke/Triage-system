"""Interactive triage in the terminal, using the protocols in the database.

    python -m scripts.triage_cli

This is a demo of the decision engine before the web screens are built.
It does not save anything to the database.
"""
from sqlalchemy import select

from app.database import SessionLocal
from app.engine import NextQuestion, evaluate, rules_from_db
from app.models import Protocol

LABEL = {"emergency": "EMERGENCY", "urgent": "URGENT", "routine": "ROUTINE", "self_care": "SELF-CARE"}
LINE = "-" * 64


def ask(prompt: str, allowed: set[str]) -> str:
    while True:
        value = input(prompt).strip().lower()
        if value in allowed:
            return value
        print(f"  Please type one of: {', '.join(sorted(allowed))}")


def main() -> None:
    with SessionLocal() as db:
        protocols = db.scalars(select(Protocol).where(Protocol.is_active).order_by(Protocol.protocol_id)).all()
        if not protocols:
            print("No protocols found. Run: python -m scripts.seed")
            return
        print(LINE + "\n NURSE TELEPHONE TRIAGE  (demo, nothing is saved)\n" + LINE)
        if ask("Has the caller agreed to the call being recorded? (y/n): ", {"y", "n"}) == "n":
            print("\nConsent not given. End the call. No data is stored.")
            return
        print("\nSelect the protocol for the caller's main symptom:")
        for i, p in enumerate(protocols, start=1):
            print(f"  {i:>2}. {p.name}")
        choice = int(ask("Number: ", {str(i) for i in range(1, len(protocols) + 1)}))
        rules = rules_from_db(protocols[choice - 1])

    print(f"\n{rules.name}\nAnswer y (yes), n (no), or b (back).\n")
    answers: dict[int, bool] = {}
    while True:
        step = evaluate(rules, answers)
        if not isinstance(step, NextQuestion):
            break
        q = step.question
        reply = ask(f"Q{step.number} of {step.total}. {q.text}\n  > ", {"y", "n", "b"})
        if reply == "b":
            if answers:
                answers.pop(max(answers))
            continue
        answers[q.order] = reply == "y"

    r = step
    print("\n" + LINE)
    print(f" RESULT: {LABEL[r.level]}")
    if r.triggered_by:
        print(f" Because: Q{r.triggered_by.order} was answered Yes")
    else:
        print(" Because: every answer was No")
    print(LINE + "\n Care advice to read to the caller:")
    for i, line in enumerate(r.advice, start=1):
        print(f"  {i}. {line}")
    print(LINE)


if __name__ == "__main__":
    main()
