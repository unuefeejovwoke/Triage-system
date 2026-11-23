"""Load the four disposition levels and all protocol files into the database.

Run from the project folder:
    python -m scripts.seed

Safe to run more than once. A protocol that is already in the database with
the same name and version is skipped, so nothing is duplicated. To load a
changed protocol, raise its "version" number in the JSON file first.
"""
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Disposition, Protocol, TriageQuestion
from app.protocol_store import ensure_dispositions, fill_protocol
from app.protocols import load_all


def seed_dispositions(db) -> dict[str, Disposition]:
    return ensure_dispositions(db)


def seed_protocols(db, dispositions: dict[str, Disposition]) -> tuple[int, int]:
    added = skipped = 0
    for data in load_all():
        found = db.scalar(select(Protocol).where(Protocol.name == data["name"], Protocol.version == data["version"]))
        if found:
            skipped += 1
            continue
        db.add(fill_protocol(Protocol(is_active=True), data, dispositions))
        added += 1
    db.flush()
    return added, skipped


def main() -> None:
    with SessionLocal() as db:
        dispositions = seed_dispositions(db)
        added, skipped = seed_protocols(db, dispositions)
        db.commit()
        total_q = db.query(TriageQuestion).count()
    print(f"Dispositions ready: {len(dispositions)}")
    print(f"Protocols added: {added}, already present: {skipped}")
    print(f"Triage questions in database: {total_q}")


if __name__ == "__main__":
    main()
