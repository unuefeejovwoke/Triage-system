"""Save protocols to the database. Used by the seed script and the admin API."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareAdvice, Disposition, Protocol, TriageQuestion
from app.protocols import DISPOSITIONS, validate


def ensure_dispositions(db: Session) -> dict[str, Disposition]:
    existing = {d.level: d for d in db.scalars(select(Disposition))}
    for level, rank, description in DISPOSITIONS:
        if level not in existing:
            d = Disposition(level=level, severity_rank=rank, description=description)
            db.add(d)
            existing[level] = d
    db.flush()
    return existing


def fill_protocol(protocol: Protocol, data: dict, dispositions: dict[str, Disposition]) -> Protocol:
    """Copy validated protocol data onto a Protocol row, replacing its questions and advice."""
    validate(data, data.get("name", "<protocol>"))
    protocol.name = data["name"]
    protocol.version = data["version"]
    protocol.population = data["population"]
    protocol.source_guidance = data["source_guidance"]
    protocol.questions = [
        TriageQuestion(question_order=q["order"], question_text=q["text"], disposition=dispositions[q["disposition"]])
        for q in sorted(data["questions"], key=lambda q: q["order"])
    ]
    protocol.advice = [
        CareAdvice(disposition=dispositions[level], advice_text="\n".join(lines))
        for level, lines in data["advice"].items()
    ]
    return protocol
