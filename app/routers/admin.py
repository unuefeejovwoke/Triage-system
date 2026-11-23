"""Administrator functions: users, protocols, and the audit log."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log
from app.deps import get_db
from app.models import AuditLog, Consultation, Protocol, User
from app.retention import purge_old_consultations
from app.routers.consultations import _detail
from app.protocol_store import ensure_dispositions, fill_protocol
from app.protocols import ProtocolError
from app.routers.protocols import detail, summary
from app.schemas import AuditOut, ProtocolDetail, ProtocolIn, ProtocolSummary, UserCreate, UserOut, UserUpdate
from app.security import hash_password, require_role

router = APIRouter(prefix="/admin", tags=["Administration"])
admin_only = require_role("admin")


# ---------------------------------------------------------------- users

@router.get("/users", response_model=list[UserOut], summary="List users")
def list_users(db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return db.scalars(select(User).order_by(User.user_id)).all()


@router.post("/users", response_model=UserOut, status_code=201, summary="Create a user")
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    email = body.email.lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    user = User(full_name=body.full_name, email=email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    db.flush()
    log(db, admin.user_id, "user_created", f"user:{user.user_id}")
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=UserOut, summary="Update a user")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found.")
    if user.user_id == admin.user_id and (body.is_active is False or body.role == "nurse"):
        raise HTTPException(status.HTTP_409_CONFLICT, "You cannot deactivate or demote your own account.")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    log(db, admin.user_id, "user_updated", f"user:{user.user_id}")
    db.commit()
    return user


# ---------------------------------------------------------------- protocols

def _protocol_error(e: ProtocolError) -> HTTPException:
    return HTTPException(422, {"message": "Protocol failed the safety check.",
                                                                 "problems": e.problems})


@router.get("/protocols", response_model=list[ProtocolSummary], summary="List all protocols, including inactive")
def all_protocols(db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    return [summary(p) for p in db.scalars(select(Protocol).order_by(Protocol.protocol_id))]


@router.post("/protocols", response_model=ProtocolDetail, status_code=201, summary="Create a protocol")
def create_protocol(body: ProtocolIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    data = body.model_dump()
    if db.scalar(select(Protocol).where(Protocol.name == data["name"], Protocol.version == data["version"])):
        raise HTTPException(status.HTTP_409_CONFLICT, "A protocol with this name and version already exists.")
    try:
        p = fill_protocol(Protocol(is_active=True), data, ensure_dispositions(db))
    except ProtocolError as e:
        raise _protocol_error(e)
    db.add(p)
    db.flush()
    log(db, admin.user_id, "protocol_created", f"protocol:{p.protocol_id}")
    db.commit()
    return detail(p)


@router.put("/protocols/{protocol_id}", response_model=ProtocolDetail, summary="Edit a protocol")
def update_protocol(protocol_id: int, body: ProtocolIn, db: Session = Depends(get_db),
                    admin: User = Depends(admin_only)):
    """A protocol already used in a consultation cannot be edited, so old records stay accurate.
    Save the change as a new version instead, then deactivate the old one."""
    p = db.get(Protocol, protocol_id)
    if p is None:
        raise HTTPException(404, "Protocol not found.")
    if db.scalar(select(func.count()).select_from(Consultation).where(Consultation.protocol_id == protocol_id)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This protocol has been used in consultations. Save your changes as a new version.")
    try:
        fill_protocol(p, body.model_dump(), ensure_dispositions(db))
    except ProtocolError as e:
        db.rollback()
        raise _protocol_error(e)
    log(db, admin.user_id, "protocol_updated", f"protocol:{p.protocol_id}")
    db.commit()
    return detail(p)


@router.patch("/protocols/{protocol_id}/active", response_model=ProtocolSummary, summary="Activate or deactivate")
def set_active(protocol_id: int, active: bool, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    p = db.get(Protocol, protocol_id)
    if p is None:
        raise HTTPException(404, "Protocol not found.")
    p.is_active = active
    log(db, admin.user_id, "protocol_activated" if active else "protocol_deactivated", f"protocol:{p.protocol_id}")
    db.commit()
    return summary(p)


# ---------------------------------------------------------------- data subject rights (NDPA 2023)

@router.get("/consultations/{consultation_id}/export", summary="Export one consultation record as JSON")
def export_consultation(consultation_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """Supports a data subject's request for a copy of their record."""
    c = db.get(Consultation, consultation_id)
    if c is None:
        raise HTTPException(404, "Consultation not found.")
    data = _detail(c, db).model_dump(mode="json")
    log(db, admin.user_id, "consultation_exported", c.caller_ref)
    db.commit()
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{c.caller_ref}.json"'})


@router.delete("/consultations/{consultation_id}", status_code=204, summary="Erase one consultation record")
def erase_consultation(consultation_id: int, reason: str = Query(min_length=10, max_length=300),
                       db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """Supports a data subject's request for erasure. The record and its answers are deleted.
    The audit log keeps only the caller reference and the fact that it was erased."""
    c = db.get(Consultation, consultation_id)
    if c is None:
        raise HTTPException(404, "Consultation not found.")
    ref = c.caller_ref
    db.delete(c)
    log(db, admin.user_id, "consultation_erased", f"{ref}: {reason.strip()}")
    db.commit()


@router.post("/retention/purge", summary="Delete consultations older than the retention period")
def purge(dry_run: bool = True, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    """With dry_run=true (the default), only counts what would be deleted."""
    return purge_old_consultations(db, dry_run=dry_run, user_id=admin.user_id)


# ---------------------------------------------------------------- audit log

@router.get("/audit-logs", response_model=list[AuditOut], summary="View the audit log")
def audit_logs(limit: int = 200, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    rows = db.execute(
        select(AuditLog, User.full_name).outerjoin(User, AuditLog.user_id == User.user_id)
        .order_by(AuditLog.log_id.desc()).limit(min(max(limit, 1), 1000))
    ).all()
    return [AuditOut(log_id=a.log_id, user_id=a.user_id, user_name=name, action=a.action,
                     entity=a.entity, created_at=a.created_at) for a, name in rows]
