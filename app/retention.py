"""Storage limitation (NDPA 2023): delete consultation records older than the retention period.

The period is set by RETENTION_DAYS in .env. It is a decision for the organisation
running the service, made with its data protection officer.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.audit import log
from app.config import settings
from app.models import Consultation


def purge_old_consultations(db: Session, dry_run: bool = True, user_id: int | None = None,
                            days: int | None = None) -> dict:
    days = days if days is not None else settings.retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if db.bind.dialect.name == "sqlite":
        cutoff = cutoff.replace(tzinfo=None)
    old = db.scalars(select(Consultation).where(or_(
        Consultation.ended_at < cutoff,
        Consultation.ended_at.is_(None) & (Consultation.started_at < cutoff),
    ))).all()
    result = {"retention_days": days, "cutoff": cutoff.date().isoformat(), "matched": len(old), "deleted": 0, "dry_run": dry_run}
    if not dry_run and old:
        for c in old:
            db.delete(c)
        result["deleted"] = len(old)
        log(db, user_id, "retention_purge", f"{len(old)} consultations before {result['cutoff']}")
        db.commit()
    return result
