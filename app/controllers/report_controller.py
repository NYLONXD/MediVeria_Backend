import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_card_verified, require_processing_queue
from app.models.user import User
from app.schemas.report import ReportCreate, ReportOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.list_reports(db, current_user)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return report_service.get_report(db, current_user, report_id)


@router.post("", response_model=ReportOut, status_code=201)
def upload_report(
    payload: Annotated[str, Form(...)],
    files: Annotated[list[UploadFile], File(...)],
    _: None = Depends(require_processing_queue),
    db: Session = Depends(get_db),
    # RFID confirmation is intentionally not required for the prototype.
    # report_service still verifies that the authenticated user is a doctor.
    current_user: User = Depends(get_current_user),
):
    report_in = ReportCreate.model_validate(json.loads(payload))
    return report_service.create_report(db, current_user, report_in, files)


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_card_verified),
):
    report_service.delete_report(db, current_user, report_id)
