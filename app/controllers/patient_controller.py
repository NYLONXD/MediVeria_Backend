from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.patient import PatientOut

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("", response_model=list[PatientOut])
def list_patients(
    search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _current_user=Depends(require_role("doctor", "admin", "hospital_admin")),
):
    query = db.query(User).filter(User.role == UserRole.patient, User.is_active.is_(True))
    search_term = (search or "").strip()
    if search_term:
        pattern = f"%{search_term}%"
        query = query.filter(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
                cast(User.id, String).ilike(pattern),
            )
        )

    return query.order_by(User.full_name.asc()).limit(100).all()