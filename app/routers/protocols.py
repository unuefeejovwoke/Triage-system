"""Read protocols. Available to nurses and administrators."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import Protocol, User
from app.schemas import ProtocolDetail, ProtocolSummary, QuestionOut
from app.security import get_current_user

router = APIRouter(prefix="/protocols", tags=["Protocols"])


def summary(p: Protocol) -> ProtocolSummary:
    return ProtocolSummary(protocol_id=p.protocol_id, name=p.name, population=p.population,
                           version=p.version, question_count=len(p.questions), is_active=p.is_active)


def detail(p: Protocol) -> ProtocolDetail:
    advice = {a.disposition.level: a.advice_text.splitlines()
              for a in sorted(p.advice, key=lambda a: a.disposition.severity_rank)}
    return ProtocolDetail(
        **summary(p).model_dump(), source_guidance=p.source_guidance,
        questions=[QuestionOut(question_id=q.question_id, order=q.question_order,
                               text=q.question_text, level=q.disposition.level) for q in p.questions],
        advice=advice,
    )


@router.get("", response_model=list[ProtocolSummary], summary="List active protocols")
def list_protocols(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Protocol).where(Protocol.is_active).order_by(Protocol.protocol_id)).all()
    return [summary(p) for p in rows]


@router.get("/{protocol_id}", response_model=ProtocolDetail, summary="One protocol with its questions")
def get_protocol(protocol_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(Protocol, protocol_id)
    if p is None:
        raise HTTPException(404, "Protocol not found.")
    return detail(p)
