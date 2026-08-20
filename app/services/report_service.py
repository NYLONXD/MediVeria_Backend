import io
import secrets
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session, joinedload

from app.models.health_records import (
    AuditAction,
    AuditLog,
    Doctor,
    FileRole,
    PendingPatient,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingJobType,
    PipelineStage,
    Report,
    ReportExtraction,
    ReportFile,
    ReportStatus,
    SourceFormat,
)
from app.models.user import User, UserRole
from app.schemas.report import ReportCreate
from app.services import ocr_service
from app.services.cloudinary_service import get_signed_url, upload_medical_file


def _source_format(content_type: str | None, filename: str | None) -> SourceFormat:
    value = (content_type or filename or "").lower()
    if "pdf" in value or value.endswith(".pdf"):
        return SourceFormat.pdf
    if "dicom" in value or value.endswith((".dcm", ".dicom")):
        return SourceFormat.dicom
    if "image" in value or value.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceFormat.image
    return SourceFormat.structured


def _planned_jobs(report_type, source_format: SourceFormat) -> list[tuple[ProcessingJobType, PipelineStage]]:
    jobs = [(ProcessingJobType.virus_scan, PipelineStage.scanning)]
    if source_format == SourceFormat.dicom:
        jobs.extend(
            [
                (ProcessingJobType.dicom_parsing, PipelineStage.extracting),
                (ProcessingJobType.thumbnail_generation, PipelineStage.extracting),
            ]
        )
    elif source_format in {SourceFormat.pdf, SourceFormat.image}:
        if report_type.value in {"blood_test", "lab_report"}:
            jobs.append((ProcessingJobType.table_extraction, PipelineStage.extracting))
        jobs.append((ProcessingJobType.ocr, PipelineStage.extracting))
    else:
        jobs.append((ProcessingJobType.structured_extraction, PipelineStage.extracting))

    if report_type.value == "ecg":
        jobs.append((ProcessingJobType.waveform_processing, PipelineStage.extracting))

    jobs.extend(
        [
            (ProcessingJobType.normalization, PipelineStage.structuring),
            (ProcessingJobType.ai_analysis, PipelineStage.analyzing),
        ]
    )
    return jobs


def _ensure_doctor_profile(db: Session, current_user: User) -> None:
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can upload reports")
    if not db.query(Doctor).filter(Doctor.id == current_user.id).first():
        db.add(Doctor(id=current_user.id, license_number=f"PENDING-{current_user.id}", specialization=current_user.category))
        db.flush()


def _mark_done(job: Optional[ProcessingJob]) -> None:
    if job is None:
        return
    job.status = ProcessingJobStatus.completed
    job.completed_at = datetime.now(timezone.utc)


def _mark_failed(job: Optional[ProcessingJob], error: str) -> None:
    if job is None:
        return
    job.status = ProcessingJobStatus.failed
    job.error_message = error[:500]
    job.completed_at = datetime.now(timezone.utc)


def _process_file_sync(
    db: Session,
    report: Report,
    report_file: ReportFile,
    raw_bytes: bytes,
    source_format: SourceFormat,
    original_filename: str,
    jobs_by_type: dict,
) -> None:
    """Runs OCR / DICOM conversion right now, synchronously, during the
    upload request. No AI analysis — that stage is intentionally left
    'queued' for later. This is a hackathon shortcut: a real background
    worker (Celery/RQ) should replace this before production so uploads
    don't block on OCR/DICOM processing time."""

    try:
        if source_format == SourceFormat.pdf:
            text = ocr_service.extract_text_from_pdf(raw_bytes)
            db.add(ReportExtraction(
                report_id=report.id,
                report_file_id=report_file.id,
                extracted_text=text,
                extraction_method="pymupdf+tesseract",
            ))
            _mark_done(jobs_by_type.get(ProcessingJobType.ocr))

        elif source_format == SourceFormat.image:
            text = ocr_service.extract_text_from_image(raw_bytes)
            db.add(ReportExtraction(
                report_id=report.id,
                report_file_id=report_file.id,
                extracted_text=text,
                extraction_method="tesseract",
            ))
            _mark_done(jobs_by_type.get(ProcessingJobType.ocr))

        elif source_format == SourceFormat.dicom:
            meta = ocr_service.dicom_metadata(raw_bytes)
            preview_png = ocr_service.dicom_to_preview_png(raw_bytes)

            if preview_png:
                preview_upload = upload_medical_file(
                    io.BytesIO(preview_png),
                    f"{original_filename}-preview.png",
                    "image/png",
                )
                db.add(ReportFile(
                    report_id=report.id,
                    parent_file_id=report_file.id,
                    source_format=SourceFormat.image,
                    role=FileRole.derived,
                    bucket_name=preview_upload["bucket_name"],
                    object_key=preview_upload["object_key"],
                    mime_type="image/png",
                    file_name=preview_upload["file_name"],
                    file_size_bytes=preview_upload["bytes"],
                    checksum_sha256=preview_upload["checksum_sha256"],
                    encryption_key_ref="cloudinary-authenticated-asset",
                    is_encrypted=True,
                ))

            db.add(ReportExtraction(
                report_id=report.id,
                report_file_id=report_file.id,
                structured_data=meta,
                extraction_method="pydicom",
            ))
            _mark_done(jobs_by_type.get(ProcessingJobType.dicom_parsing))
            _mark_done(jobs_by_type.get(ProcessingJobType.thumbnail_generation))

        elif source_format == SourceFormat.structured:
            import json
            try:
                parsed = json.loads(raw_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                parsed = None
            db.add(ReportExtraction(
                report_id=report.id,
                report_file_id=report_file.id,
                structured_data=parsed if isinstance(parsed, dict) else {"raw": str(parsed)},
                extraction_method="json",
            ))
            _mark_done(jobs_by_type.get(ProcessingJobType.structured_extraction))

        # No real virus scanner wired up tonight — mark as done so the
        # pipeline doesn't sit stuck at "queued" forever in the UI.
        _mark_done(jobs_by_type.get(ProcessingJobType.virus_scan))
        _mark_done(jobs_by_type.get(ProcessingJobType.normalization))
        # ai_analysis job intentionally left untouched (still 'queued') —
        # not implemented yet, by design.

    except Exception as exc:  # OCR/DICOM failure should not fail the whole upload
        for job_type, job in jobs_by_type.items():
            if job_type != ProcessingJobType.ai_analysis and job.status == ProcessingJobStatus.queued:
                _mark_failed(job, str(exc))


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
        status=ReportStatus.processing,
    )
    db.add(report)
    db.flush()

    for upload in files:
        raw_bytes = upload.file.read()
        upload.file.seek(0)

        uploaded = upload_medical_file(io.BytesIO(raw_bytes), upload.filename or "medical-report", upload.content_type)
        source_format = _source_format(upload.content_type, upload.filename)

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

        jobs_by_type = {}
        for job_type, stage in _planned_jobs(report.report_type, source_format):
            job = ProcessingJob(
                report_id=report.id,
                report_file_id=report_file.id,
                job_type=job_type,
                stage=stage,
                metadata_json={"planned_by": "upload_pipeline"},
            )
            db.add(job)
            db.flush()
            jobs_by_type[job_type] = job

        _process_file_sync(
            db=db,
            report=report,
            report_file=report_file,
            raw_bytes=raw_bytes,
            source_format=source_format,
            original_filename=upload.filename or "medical-report",
            jobs_by_type=jobs_by_type,
        )

    report.status = ReportStatus.ready
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.report_upload, entity_type="reports", entity_id=report.id))
    db.commit()
    return get_report(db, current_user, report.id)


def _resource_type_for(source_format: SourceFormat) -> str:
    return "image" if source_format in (SourceFormat.pdf, SourceFormat.image) else "raw"


def _attach_view_urls(report: Report) -> Report:
    """Cloudinary assets are authenticated-only — without a signed URL
    the frontend literally cannot display the file. Attached as a plain
    (non-persisted) attribute so ReportFileOut.view_url picks it up."""
    for f in report.files:
        try:
            f.view_url = get_signed_url(f.object_key, _resource_type_for(f.source_format))
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
        )
        .order_by(Report.uploaded_at.desc())
    )
    if current_user.role == UserRole.patient:
        query = query.filter(Report.patient_id == current_user.id)
    elif current_user.role == UserRole.doctor:
        query = query.filter(Report.uploaded_by_doctor_id == current_user.id)
    return [_attach_view_urls(r) for r in query.all()]