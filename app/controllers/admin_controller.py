from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_role
from app.schemas.card import CardAssignRequest
from app.services import card_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/doctors/{doctor_id}/card")
def assign_card(
    doctor_id: str,
    payload: CardAssignRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
):
    doctor = card_service.assign_card_to_doctor(db, doctor_id, payload.card_uid)
    return {"message": "Card assigned", "doctor_id": str(doctor.id)}