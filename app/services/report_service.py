import io
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
    ProcessingJob,
    Report,
    ReportFile,
    ReportStatus,
    SourceFormat,
)
from app.models.user import User, UserRole
from app.schemas.report import ReportCreate
from app.services.cloudinary_service import get_signed_url, resource_type_for_source_format, upload_medical_file
from app.services.pipeline_planning import detect_source_format, plan_jobs


def _ensure_doctor_profile(db: Session, current_user: User) -> None:
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can upload reports")
    if not db.query(Doctor).filter(Doctor.id == current_user.id).first():
        db.add(Doctor(id=current_user.id, license_number=f"PENDING-{current_user.id}", specialization=current_user.category))
        db.flush()


def create_report(db: Session, current_user: User, report_in: ReportCreate, files: Iterable[UploadFile]) -> Report:
    # Imported here, not at module load time, to avoid the FastAPI process
    # needing the full Celery/worker import chain resolved before it can
    # even start up if something in that chain is briefly broken.
    from app.workers.tasks import run_processing_job

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
        status=ReportStatus.processing,  # stays "processing" until the worker chain finishes
    )
    db.add(report)
    db.flush()

    first_job_ids: list = []

    for upload in files:
        raw_bytes = upload.file.read()
        upload.file.seek(0)

        uploaded = upload_medical_file(io.BytesIO(raw_bytes), upload.filename or "medical-report", upload.content_type)
        source_format = detect_source_format(upload.content_type, upload.filename)

        report_file = ReportFile(
            report_id=report.id,
            source_format=source_format,
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
        db.add(report_file)
        db.flush()

        job_rows = []
        for job_type, stage in plan_jobs(report.report_type, source_format):
            job = ProcessingJob(
                report_id=report.id,
                report_file_id=report_file.id,
                job_type=job_type,
                stage=stage,
                metadata_json={"planned_by": "upload_pipeline"},
            )
            db.add(job)
            db.flush()
            job_rows.append(job)

        # Chain the jobs: each one records the id of the next so the
        # worker knows what to enqueue when it finishes.
        for i in range(len(job_rows) - 1):
            current = job_rows[i]
            current.metadata_json = {**(current.metadata_json or {}), "next_job_id": str(job_rows[i + 1].id)}
        db.flush()

        first_job_ids.append(job_rows[0].id)  # always virus_scan — the chain always starts there

    db.add(AuditLog(user_id=current_user.id, action=AuditAction.report_upload, entity_type="reports", entity_id=report.id))
    db.commit()

    # Enqueue only AFTER commit: the worker runs in a separate process and
    # must be able to see these rows the moment it picks the job up.
    for job_id in first_job_ids:
        run_processing_job.delay(str(job_id))

    return get_report(db, current_user, report.id)


def _attach_view_urls(report: Report) -> Report:
    """Files are Cloudinary `authenticated` assets — without a signed URL
    the frontend has no way to display them at all. Attached as a plain
    (non-persisted) instance attribute; ReportFileOut.view_url reads it
    via from_attributes."""
    for f in report.files:
        if f.is_quarantined:
            f.view_url = None
            continue
        try:
            f.view_url = get_signed_url(f.object_key, resource_type_for_source_format(f.source_format))
        except Exception:
            f.view_url = None
    return report


def get_report(db: Session, current_user: User, report_id) -> Report:
    report = (
        db.query(Report)
        .options(
            joinedload(Report.files),
            joinedload(Report.processing_jobs),
            joinedload(Report.extractions),
            joinedload(Report.measurements),
        )
        .filter(Report.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role == UserRole.patient and report.patient_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot access this report")
    return _attach_view_urls(report)


def list_reports(db: Session, current_user: User) -> list[Report]:
    query = (
        db.query(Report)
        .options(
            joinedload(Report.files),
            joinedload(Report.processing_jobs),
            joinedload(Report.extractions),
            joinedload(Report.measurements),
        )
        .order_by(Report.uploaded_at.desc())
    )
    if current_user.role == UserRole.patient:
        query = query.filter(Report.patient_id == current_user.id)
    elif current_user.role == UserRole.doctor:
        query = query.filter(Report.uploaded_by_doctor_id == current_user.id)
    return [_attach_view_urls(r) for r in query.all()]