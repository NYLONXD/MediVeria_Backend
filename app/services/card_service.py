from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.health_records import Doctor


def assign_card_to_doctor(db: Session, doctor_id, card_uid: str) -> Doctor:
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    clash = db.query(Doctor).filter(Doctor.card_uid == card_uid, Doctor.id != doctor_id).first()
    if clash:
        raise HTTPException(status_code=400, detail="This card is already assigned to another doctor")

    doctor.card_uid = card_uid
    doctor.card_registered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(doctor)
    return doctor