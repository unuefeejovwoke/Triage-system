"""Print protocols from the database so you can check them.

    python -m scripts.show_protocol            # list all protocols
    python -m scripts.show_protocol "Chest"    # show one protocol in full
"""
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Protocol

LABEL = {"emergency": "EMERGENCY", "urgent": "URGENT", "routine": "ROUTINE", "self_care": "SELF-CARE"}


def main() -> None:
    term = " ".join(sys.argv[1:]).strip().lower()
    with SessionLocal() as db:
        protocols = db.scalars(select(Protocol).order_by(Protocol.protocol_id)).all()
        if not protocols:
            print("No protocols found. Run: python -m scripts.seed")
            return
        if not term:
            print(f"{'ID':<4}{'Protocol':<48}{'For':<18}{'Questions':>9}")
            for p in protocols:
                print(f"{p.protocol_id:<4}{p.name:<48}{p.population:<18}{len(p.questions):>9}")
            return
        for p in protocols:
            if term not in p.name.lower():
                continue
            print(f"\n{p.name}  (v{p.version}, {p.population})")
            print(f"Source: {p.source_guidance}\n")
            for q in p.questions:
                print(f"  Q{q.question_order}. {q.question_text}")
                print(f"       If YES -> {LABEL[q.disposition.level]}")
            print("  If NO to every question -> SELF-CARE\n")
            for a in sorted(p.advice, key=lambda a: a.disposition.severity_rank):
                print(f"  Advice for {LABEL[a.disposition.level]}:")
                for line in a.advice_text.splitlines():
                    print(f"    - {line}")
            return
        print(f"No protocol matches '{term}'.")


if __name__ == "__main__":
    main()
