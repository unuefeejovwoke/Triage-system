"""Write entries to the audit log (accountability under the NDPA 2023)."""
from sqlalchemy.orm import Session

from app.models import AuditLog


def log(db: Session, user_id: int | None, action: str, entity: str) -> None:
    db.add(AuditLog(user_id=user_id, action=action[:60], entity=entity[:60]))
