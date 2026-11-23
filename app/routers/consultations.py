"""Consultations: one telephone call, from consent to the saved result.

Flow used by the nurse's screen:
    POST /consultations                       start the call, get the first question
    POST /consultations/{id}/answers          answer the current question, get the next step
    DELETE /consultations/{id}/answers/last   go back one question
    POST /consultations/{id}/finalize         accept the result, or override it with a reason
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log
from app.deps import get_db
from app.engine import NextQuestion, evaluate, rules_from_db
from app.models import Consultation, ConsultationAnswer, Disposition, Protocol, User
from app.schemas import (
    AnswerIn, AnswerOut, ConsultationDetail, ConsultationStart, ConsultationSummary, Finalize,
    NextQuestionOut, QuestionOut, ResultOut,
)
from app.security import get_current_user, require_role

router = APIRouter(prefix="/consultations", tags=["Consultations"])


# ---------------------------------------------------------------- helpers

def _answers(c: Consultation) -> dict[int, bool]:
    orders = {q.question_id: q.question_order for q in c.protocol.questions}
    return {orders[a.question_id]: a.answer for a in c.answers}


def _step(c: Consultation) -> NextQuestionOut | ResultOut:
    protocol = c.protocol
    rules = rules_from_db(protocol)
    ids = {q.question_order: q.question_id for q in protocol.questions}
    step = evaluate(rules, _answers(c))

    def q_out(q):
        return QuestionOut(question_id=ids[q.order], order=q.order, text=q.text, level=q.level)

    if isinstance(step, NextQuestion):
        return NextQuestionOut(question=q_out(step.question), number=step.number, total=step.total)
    return ResultOut(level=step.level, severity_rank=step.severity_rank,
                     triggered_by=q_out(step.triggered_by) if step.triggered_by else None,
                     advice=list(step.advice), questions_asked=step.questions_asked)


def _summary(c: Consultation, db: Session) -> dict:
    p, final = c.protocol, c.final_disposition
    return dict(consultation_id=c.consultation_id, protocol_id=c.protocol_id, caller_ref=c.caller_ref, caller_age=c.caller_age,
                caller_sex=c.caller_sex, protocol_name=p.name if p else None,
                final_level=final.level if final else None, overridden=c.overridden,
                nurse=c.user.full_name, started_at=c.started_at, ended_at=c.ended_at)


def _detail(c: Consultation, db: Session) -> ConsultationDetail:
    questions = {q.question_id: q for q in c.protocol.questions}
    answers = sorted(
        (AnswerOut(question_id=a.question_id, order=questions[a.question_id].question_order,
                   text=questions[a.question_id].question_text, answer=a.answer, answered_at=a.answered_at)
         for a in c.answers),
        key=lambda a: a.order,
    )
    return ConsultationDetail(**_summary(c, db), consent_given=c.consent_given,
                              override_reason=c.override_reason, answers=answers, step=_step(c))


def _get_own(db: Session, consultation_id: int, user: User) -> Consultation:
    c = db.get(Consultation, consultation_id)
    if c is None:
        raise HTTPException(404, "Consultation not found.")
    if user.role != "admin" and c.user_id != user.user_id:
        raise HTTPException(403, "You can only open your own consultations.")
    return c


def _open_for_editing(db: Session, consultation_id: int, user: User) -> Consultation:
    c = _get_own(db, consultation_id, user)
    if c.user_id != user.user_id:
        raise HTTPException(403, "Only the nurse who started this consultation can change it.")
    if c.ended_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This consultation is already closed.")
    return c


# ---------------------------------------------------------------- endpoints

@router.post("", response_model=ConsultationDetail, status_code=201, summary="Start a consultation")
def start(body: ConsultationStart, db: Session = Depends(get_db), user: User = Depends(require_role("nurse"))):
    if not body.consent_given:
        log(db, user.user_id, "consent_declined", "consultation")
        db.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Consent not given. End the call. No data is stored.")
    protocol = db.get(Protocol, body.protocol_id)
    if protocol is None or not protocol.is_active:
        raise HTTPException(404, "Protocol not found or not active.")
    c = Consultation(user_id=user.user_id, protocol_id=protocol.protocol_id, caller_ref="pending",
                     caller_age=body.caller_age, caller_sex=body.caller_sex, consent_given=True)
    db.add(c)
    db.flush()
    c.caller_ref = f"C-{c.consultation_id:06d}"
    log(db, user.user_id, "consultation_started", c.caller_ref)
    db.commit()
    return _detail(c, db)


@router.get("", response_model=list[ConsultationSummary], summary="List past consultations")
def list_consultations(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = select(Consultation).order_by(Consultation.consultation_id.desc()).limit(min(max(limit, 1), 500))
    if user.role != "admin":
        q = q.where(Consultation.user_id == user.user_id)
    return [ConsultationSummary(**_summary(c, db)) for c in db.scalars(q)]


@router.get("/{consultation_id}", response_model=ConsultationDetail, summary="One consultation in full")
def get_consultation(consultation_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _get_own(db, consultation_id, user)
    if c.user_id != user.user_id:
        # Someone other than the treating nurse opened a health record: keep a trace (NDPA accountability).
        log(db, user.user_id, "consultation_viewed", c.caller_ref)
        db.commit()
    return _detail(c, db)


@router.post("/{consultation_id}/answers", response_model=NextQuestionOut | ResultOut,
             summary="Answer the current question and get the next step")
def answer(consultation_id: int, body: AnswerIn, db: Session = Depends(get_db),
           user: User = Depends(require_role("nurse"))):
    c = _open_for_editing(db, consultation_id, user)
    step = _step(c)
    if step.done:
        raise HTTPException(status.HTTP_409_CONFLICT, "A result has already been reached. Finalize the consultation.")
    if body.question_id != step.question.question_id:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Answer the current question first (question {step.question.order}).")
    db.add(ConsultationAnswer(consultation_id=c.consultation_id, question_id=body.question_id, answer=body.answer))
    db.commit()
    db.refresh(c)
    return _step(c)


@router.delete("/{consultation_id}/answers/last", response_model=NextQuestionOut,
               summary="Go back one question")
def undo_last(consultation_id: int, db: Session = Depends(get_db), user: User = Depends(require_role("nurse"))):
    c = _open_for_editing(db, consultation_id, user)
    if not c.answers:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no answer to undo.")
    orders = {q.question_id: q.question_order for q in c.protocol.questions}
    last = max(c.answers, key=lambda a: orders[a.question_id])
    db.delete(last)
    db.commit()
    db.refresh(c)
    return _step(c)


@router.post("/{consultation_id}/finalize", response_model=ConsultationDetail,
             summary="Accept the result, or override it with a reason")
def finalize(consultation_id: int, body: Finalize, db: Session = Depends(get_db),
             user: User = Depends(require_role("nurse"))):
    c = _open_for_editing(db, consultation_id, user)
    step = _step(c)
    if not step.done:
        raise HTTPException(status.HTTP_409_CONFLICT, "Finish the triage questions before saving a result.")
    level = step.level if body.accept else body.override_level
    disposition = db.scalar(select(Disposition).where(Disposition.level == level))
    c.final_disposition = disposition
    c.overridden = not body.accept and level != step.level
    c.override_reason = body.override_reason.strip() if c.overridden else None
    c.ended_at = datetime.now(timezone.utc)
    if c.overridden:
        log(db, user.user_id, "disposition_overridden", f"{c.caller_ref}:{step.level}->{level}")
    log(db, user.user_id, "consultation_closed", c.caller_ref)
    db.commit()
    return _detail(c, db)
