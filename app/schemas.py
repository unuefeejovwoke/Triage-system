"""Request and response shapes for the API. Pydantic checks every request against these."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Level = Literal["emergency", "urgent", "routine", "self_care"]
Role = Literal["nurse", "admin"]
Sex = Literal["male", "female", "other", "unknown"]


# ---------------------------------------------------------------- auth and users

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    full_name: str
    email: str
    role: Role
    is_active: bool


def _check_password(value: str | None) -> str | None:
    from app.security import password_problem
    if value is not None and (problem := password_problem(value)):
        raise ValueError(problem)
    return value


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    role: Role = "nurse"

    _pw = field_validator("password")(_check_password)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None

    _pw = field_validator("password")(_check_password)


# ---------------------------------------------------------------- protocols

class QuestionOut(BaseModel):
    question_id: int
    order: int
    text: str
    level: Level


class ProtocolSummary(BaseModel):
    protocol_id: int
    name: str
    population: str
    version: str
    question_count: int
    is_active: bool


class ProtocolDetail(ProtocolSummary):
    source_guidance: str
    questions: list[QuestionOut]
    advice: dict[str, list[str]]


class ProtocolIn(BaseModel):
    """Same shape as the JSON files in data/protocols."""
    name: str = Field(min_length=2, max_length=120)
    version: str = Field(min_length=1, max_length=20)
    population: str = Field(min_length=2, max_length=40)
    source_guidance: str = Field(min_length=2)
    questions: list[dict]
    advice: dict[str, list[str]]


# ---------------------------------------------------------------- consultations

class ConsultationStart(BaseModel):
    caller_age: int = Field(ge=0, le=120)
    caller_sex: Sex
    consent_given: bool
    protocol_id: int


class AnswerIn(BaseModel):
    question_id: int
    answer: bool


class NextQuestionOut(BaseModel):
    done: Literal[False] = False
    question: QuestionOut
    number: int
    total: int


class ResultOut(BaseModel):
    done: Literal[True] = True
    level: Level
    severity_rank: int
    triggered_by: QuestionOut | None
    advice: list[str]
    questions_asked: int


class Finalize(BaseModel):
    accept: bool
    override_level: Level | None = None
    override_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_override(self):
        if not self.accept:
            if self.override_level is None:
                raise ValueError("override_level is required when overriding")
            if not (self.override_reason or "").strip():
                raise ValueError("override_reason is required when overriding")
        return self


class AnswerOut(BaseModel):
    question_id: int
    order: int
    text: str
    answer: bool
    answered_at: datetime


class ConsultationSummary(BaseModel):
    consultation_id: int
    protocol_id: int | None
    caller_ref: str
    caller_age: int
    caller_sex: Sex
    protocol_name: str | None
    final_level: Level | None
    overridden: bool
    nurse: str
    started_at: datetime
    ended_at: datetime | None


class ConsultationDetail(ConsultationSummary):
    consent_given: bool
    override_reason: str | None
    answers: list[AnswerOut]
    step: NextQuestionOut | ResultOut | None


class AuditOut(BaseModel):
    log_id: int
    user_id: int | None
    user_name: str | None
    action: str
    entity: str
    created_at: datetime
