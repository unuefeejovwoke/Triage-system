"""Database tables. These match the entity relationship diagram (Figure 3.4)."""
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ROLES = ("nurse", "admin")
LEVELS = ("emergency", "urgent", "routine", "self_care")
SEXES = ("male", "female", "other", "unknown")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="ck_users_role"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="nurse")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consultations: Mapped[list["Consultation"]] = relationship(back_populates="user")


class Disposition(Base):
    __tablename__ = "dispositions"
    __table_args__ = (
        CheckConstraint(f"level IN {LEVELS}", name="ck_dispositions_level"),
        CheckConstraint("severity_rank BETWEEN 1 AND 4", name="ck_dispositions_rank"),
    )

    disposition_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(20), unique=True)
    severity_rank: Mapped[int] = mapped_column(Integer, unique=True)  # 1 = most serious
    description: Mapped[str] = mapped_column(Text)


class Protocol(Base):
    __tablename__ = "protocols"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_protocols_name_version"),)

    protocol_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    population: Mapped[str] = mapped_column(String(40), default="adult")
    source_guidance: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), default="1.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    questions: Mapped[list["TriageQuestion"]] = relationship(
        back_populates="protocol", order_by="TriageQuestion.question_order", cascade="all, delete-orphan"
    )
    advice: Mapped[list["CareAdvice"]] = relationship(back_populates="protocol", cascade="all, delete-orphan")


class TriageQuestion(Base):
    __tablename__ = "triage_questions"
    __table_args__ = (UniqueConstraint("protocol_id", "question_order", name="uq_question_order"),)

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol_id: Mapped[int] = mapped_column(ForeignKey("protocols.protocol_id", ondelete="CASCADE"))
    disposition_id: Mapped[int] = mapped_column(ForeignKey("dispositions.disposition_id"))
    question_order: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)

    protocol: Mapped[Protocol] = relationship(back_populates="questions")
    disposition: Mapped[Disposition] = relationship()


class CareAdvice(Base):
    __tablename__ = "care_advice"
    __table_args__ = (UniqueConstraint("protocol_id", "disposition_id", name="uq_advice_protocol_disposition"),)

    advice_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    protocol_id: Mapped[int] = mapped_column(ForeignKey("protocols.protocol_id", ondelete="CASCADE"))
    disposition_id: Mapped[int] = mapped_column(ForeignKey("dispositions.disposition_id"))
    advice_text: Mapped[str] = mapped_column(Text)  # one instruction per line

    protocol: Mapped[Protocol] = relationship(back_populates="advice")
    disposition: Mapped[Disposition] = relationship()


class Consultation(Base):
    __tablename__ = "consultations"
    __table_args__ = (
        CheckConstraint(f"caller_sex IN {SEXES}", name="ck_consultations_sex"),
        CheckConstraint("caller_age BETWEEN 0 AND 120", name="ck_consultations_age"),
        CheckConstraint("overridden = false OR override_reason IS NOT NULL", name="ck_override_reason"),
    )

    consultation_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    protocol_id: Mapped[int | None] = mapped_column(ForeignKey("protocols.protocol_id"))
    final_disposition_id: Mapped[int | None] = mapped_column(ForeignKey("dispositions.disposition_id"))
    caller_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    caller_age: Mapped[int] = mapped_column(Integer)
    caller_sex: Mapped[str] = mapped_column(String(10))
    consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="consultations")
    protocol: Mapped[Protocol | None] = relationship()
    final_disposition: Mapped[Disposition | None] = relationship()
    answers: Mapped[list["ConsultationAnswer"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan"
    )


class ConsultationAnswer(Base):
    __tablename__ = "consultation_answers"
    __table_args__ = (UniqueConstraint("consultation_id", "question_id", name="uq_answer_once"),)

    answer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.consultation_id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("triage_questions.question_id"))
    answer: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consultation: Mapped[Consultation] = relationship(back_populates="answers")


class AuditLog(Base):
    __tablename__ = "audit_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
