"""Login and current user."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log
from app.config import settings
from app.deps import get_db
from app.models import AuditLog, User
from app.schemas import Token, UserOut
from app.security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _cutoff(db: Session, minutes: int) -> datetime:
    """A time in the past, in the form this database compares correctly."""
    t = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return t.replace(tzinfo=None) if db.bind.dialect.name == "sqlite" else t


def recent_failures(db: Session, email: str, user: User | None) -> int:
    """Failed sign-ins for this email in the lock window, since its last successful sign-in."""
    since = _cutoff(db, settings.login_lock_minutes)
    if user is not None:
        last_ok = db.scalar(select(func.max(AuditLog.created_at))
                            .where(AuditLog.action == "login", AuditLog.user_id == user.user_id))
        if last_ok is not None:
            last_ok = last_ok.replace(tzinfo=None) if db.bind.dialect.name == "sqlite" else last_ok
            since = max(since, last_ok)
    return db.scalar(select(func.count()).select_from(AuditLog).where(
        AuditLog.action == "login_failed", AuditLog.entity == email[:60], AuditLog.created_at > since)) or 0


@router.post("/login", response_model=Token, summary="Log in and receive a token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Send the email in the `username` field and the password in `password`.

    After several failed attempts the account is locked for a short time,
    which stops password-guessing attacks.
    """
    email = form.username.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if recent_failures(db, email, user) >= settings.login_max_attempts:
        log(db, user.user_id if user else None, "login_locked", email)
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed sign-in attempts. Try again in {settings.login_lock_minutes} minutes.")
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        log(db, user.user_id if user else None, "login_failed", email)
        db.commit()
        left = settings.login_max_attempts - recent_failures(db, email, user)
        hint = f" {left} attempt{'s' if left != 1 else ''} left before the account is locked." if 0 < left <= 2 else ""
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password." + hint,
                            headers={"WWW-Authenticate": "Bearer"})
    log(db, user.user_id, "login", "user")
    db.commit()
    return Token(access_token=create_token(user), role=user.role, full_name=user.full_name)


@router.get("/me", response_model=UserOut, summary="Who am I")
def me(user: User = Depends(get_current_user)):
    return user
