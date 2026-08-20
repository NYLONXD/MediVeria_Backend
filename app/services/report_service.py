import secrets
from typing import Iterable

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.models.health_records import (
    AuditAction,
    AuditLog,
    Doctor,
    FileRole,
    PendingPatient,
    Report,
    ReportFile,
    ReportStatus,
    SourceFormat,
)
from app.models.user import User, UserRole
from app.schemas.report import ReportCreate
from app.services.cloudinary_service import upload_medical_file


def _source_format(content_type: str | None, filename: str | None) -> SourceFormat:
    value = (content_type or filename or "").lower()
    if "pdf" in value or value.endswith(".pdf"):
        return SourceFormat.pdf
    if "dicom" in value or value.endswith((".dcm", ".dicom")):
        return SourceFormat.dicom
    if "image" in value or value.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceFormat.image
    return SourceFormat.structured


def _ensure_doctor_profile(db: Session, current_user: User) -> None:
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can upload reports")
    if not db.query(Doctor).filter(Doctor.id == current_user.id).first():
        db.add(Doctor(id=current_user.id, license_number=f"PENDING-{current_user.id}", specialization=current_user.category))
        db.flush()


def create_report(db: Session, current_user: User, report_in: ReportCreate, files: Iterable[UploadFile]) -> Report:
    _ensure_doctor_profile(db, current_user)
    if not report_in.patient_id and not report_in.pending_patient:
        raise HTTPException(status_code=400, detail="Provide patient_id or pending_patient")
    if report_in.patient_id and report_in.pending_patient:
        raise HTTPException(status_code=400, detail="Provide only one ownership route")

    pending_patient_id = None
    if report_in.pending_patient:
        pending = PendingPatient(
            full_name=report_in.pending_patient.full_name,
            phone=report_in.pending_patient.phone,
            dob=report_in.pending_patient.dob,
            hospital_id=report_in.pending_patient.hospital_id or report_in.hospital_id,
            created_by_doctor_id=current_user.id,
            claim_id=secrets.token_urlsafe(12),
        )
        db.add(pending)
        db.flush()
        pending_patient_id = pending.id

    report = Report(
        patient_id=report_in.patient_id,
        pending_patient_id=pending_patient_id,
        uploaded_by_doctor_id=current_user.id,
        hospital_id=report_in.hospital_id,
        report_type=report_in.report_type,
        title=report_in.title,
        description=report_in.description,
        report_date=report_in.report_date,
        issued_by_name=report_in.issued_by_name,
        issued_by_department=report_in.issued_by_department,
        status=ReportStatus.ready,
    )
    db.add(report)
    db.flush()

    for upload in files:
        uploaded = upload_medical_file(upload.file, upload.filename or "medical-report", upload.content_type)
        db.add(
            ReportFile(
                report_id=report.id,
                source_format=_source_format(upload.content_type, upload.filename),
                role=FileRole.original,
                bucket_name=uploaded["bucket_name"],
                object_key=uploaded["object_key"],
                mime_type=uploaded["mime_type"],
                file_name=uploaded["file_name"],
                file_size_bytes=uploaded["bytes"],
                checksum_sha256=uploaded["checksum_sha256"],
                encryption_key_ref="cloudinary-authenticated-asset",
                is_encrypted=True,
            )
        )

    db.add(AuditLog(user_id=current_user.id, action=AuditAction.report_upload, entity_type="reports", entity_id=report.id))
    db.commit()
    return get_report(db, current_user, report.id)


def get_report(db: Session, current_user: User, report_id) -> Report:
    report = db.query(Report).options(joinedload(Report.files)).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role == UserRole.patient and report.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot access this report")
    return report


def list_reports(db: Session, current_user: User) -> list[Report]:
    query = db.query(Report).options(joinedload(Report.files)).order_by(Report.uploaded_at.desc())
    if current_user.role == UserRole.patient:
        query = query.filter(Report.patient_id == current_user.id)
    elif current_user.role == UserRole.doctor:
        query = query.filter(Report.uploaded_by_doctor_id == current_user.id)
    return query.all()
