"""
The actual background pipeline. One task instance == one row in
processing_jobs. On success it looks up the next job in the chain
(stored on its own metadata_json.next_job_id) and enqueues that one —
except the last real stage (normalization), which stops the chain rather
than enqueueing ai_analysis. AI is intentionally not implemented; that
job_type simply stays "queued" forever until that's built later.

Retries are tracked in our own `attempt`/`max_attempts` columns (so the
API can show real progress), and Celery's own retry mechanism is used
just as the delivery mechanism for "try again after a backoff delay".
"""

import base64
import io
import json
from datetime import datetime, timezone

import numpy as np
import requests

from app.db.database import SessionLocal
from app.models.health_records import (
    FileRole,
    PipelineStage,
    ProcessingJob,
    ProcessingJobStatus,
    ProcessingJobType,
    Report,
    ReportExtraction,
    ReportFile,
    ReportMeasurement,
    ReportStatus,
    SourceFormat,
)
from app.services import measurement_parser, ocr_service, virus_scan_service
from app.services.cloudinary_service import (
    destroy_asset,
    get_signed_url,
    resource_type_for_source_format,
    upload_medical_file,
)
from app.workers.celery_app import celery_app

_TERMINAL_STATUSES = {ProcessingJobStatus.completed, ProcessingJobStatus.failed, ProcessingJobStatus.cancelled}


class QuarantineError(Exception):
    """Raised when a virus scan flags a file. Not a transient failure —
    never retried, and it stops the rest of that file's pipeline."""


def _download_original_bytes(report_file: ReportFile) -> bytes:
    resource_type = resource_type_for_source_format(report_file.source_format)
    url = get_signed_url(report_file.object_key, resource_type)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def _cancel_remaining_jobs_for_file(db, report_file_id, reason: str) -> None:
    still_queued = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.report_file_id == report_file_id, ProcessingJob.status == ProcessingJobStatus.queued)
        .all()
    )
    for job in still_queued:
        job.status = ProcessingJobStatus.cancelled
        job.error_message = reason
        job.completed_at = datetime.now(timezone.utc)
    db.commit()


def _maybe_finalize_report(db, report_id) -> None:
    jobs = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.report_id == report_id, ProcessingJob.job_type != ProcessingJobType.ai_analysis)
        .all()
    )
    if not jobs or not all(j.status in _TERMINAL_STATUSES for j in jobs):
        return  # still work in flight

    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        return

    any_failed = any(j.status == ProcessingJobStatus.failed for j in jobs)
    report.status = ReportStatus.failed if any_failed else ReportStatus.ready
    report.pipeline_stage = PipelineStage.failed if any_failed else PipelineStage.completed
    db.commit()


def _handle_virus_scan(db, report_file: ReportFile, raw_bytes: bytes, job: ProcessingJob) -> None:
    result = virus_scan_service.scan_bytes(raw_bytes)
    job.metadata_json = {**(job.metadata_json or {}), "scan_result": result}
    if not result["clean"]:
        report_file.is_quarantined = True
        db.commit()
        try:
            destroy_asset(report_file.object_key, resource_type_for_source_format(report_file.source_format))
        except Exception:
            pass  # best-effort cleanup — the quarantine flag is the real safeguard
        raise QuarantineError(result.get("detail", "malware detected"))


def _handle_ocr(db, report: Report, report_file: ReportFile, raw_bytes: bytes) -> None:
    if report_file.source_format == SourceFormat.pdf:
        text = ocr_service.extract_text_from_pdf(raw_bytes)
        method = "pymupdf+tesseract"
    else:
        text = ocr_service.extract_text_from_image(raw_bytes)
        method = "tesseract"
    db.add(ReportExtraction(report_id=report.id, report_file_id=report_file.id, extracted_text=text, extraction_method=method))
    db.commit()


def _handle_table_extraction(db, report: Report, report_file: ReportFile) -> None:
    extraction = (
        db.query(ReportExtraction)
        .filter(ReportExtraction.report_file_id == report_file.id, ReportExtraction.extracted_text.isnot(None))
        .order_by(ReportExtraction.created_at.desc())
        .first()
    )
    text = extraction.extracted_text if extraction else ""
    rows = measurement_parser.parse_measurements(text)
    for row in rows:
        db.add(ReportMeasurement(
            report_id=report.id,
            extraction_id=extraction.id if extraction else None,
            test_name=row["test_name"],
            value_numeric=row.get("value_numeric"),
            value_text=row.get("value_text"),
            unit=row.get("unit"),
            reference_min=row.get("reference_min"),
            reference_max=row.get("reference_max"),
            abnormal_flag=row.get("abnormal_flag"),
        ))
    db.commit()


def _handle_dicom_parsing(db, report: Report, report_file: ReportFile, raw_bytes: bytes) -> None:
    meta = ocr_service.dicom_metadata(raw_bytes)
    preview_png = ocr_service.dicom_to_preview_png(raw_bytes)

    if preview_png:
        preview_upload = upload_medical_file(
            io.BytesIO(preview_png),
            f"{report_file.file_name or 'scan'}-preview.png",
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

    db.add(ReportExtraction(report_id=report.id, report_file_id=report_file.id, structured_data=meta, extraction_method="pydicom"))
    db.commit()


def _handle_thumbnail_generation(db, report_file: ReportFile, job: ProcessingJob) -> None:
    # dicom_parsing (which always runs first for DICOM files) already
    # produces the preview image — this stage just confirms it exists
    # rather than doing redundant work.
    exists = (
        db.query(ReportFile)
        .filter(ReportFile.parent_file_id == report_file.id, ReportFile.role == FileRole.derived)
        .first()
    )
    job.metadata_json = {**(job.metadata_json or {}), "reused_dicom_parsing_preview": bool(exists)}
    db.commit()


def _handle_structured_extraction(db, report: Report, report_file: ReportFile, raw_bytes: bytes) -> None:
    try:
        parsed = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        parsed = {"raw_base64": base64.b64encode(raw_bytes).decode()}
    structured = parsed if isinstance(parsed, dict) else {"value": parsed}
    db.add(ReportExtraction(report_id=report.id, report_file_id=report_file.id, structured_data=structured, extraction_method="json"))
    db.commit()


def _handle_waveform(db, report: Report, report_file: ReportFile, raw_bytes: bytes, job: ProcessingJob) -> None:
    if report_file.source_format != SourceFormat.dicom:
        job.metadata_json = {
            **(job.metadata_json or {}),
            "skipped": True,
            "reason": (
                "Waveform digitization from a scanned image/PDF ECG strip is not implemented — "
                "only DICOM waveform objects are supported. Any OCR text is stored separately."
            ),
        }
        db.commit()
        return

    import pydicom
    ds = pydicom.dcmread(io.BytesIO(raw_bytes))
    if not hasattr(ds, "WaveformSequence"):
        job.metadata_json = {**(job.metadata_json or {}), "skipped": True, "reason": "No WaveformSequence found in DICOM file"}
        db.commit()
        return

    channels = []
    for item in ds.WaveformSequence:
        seq = getattr(item, "ChannelDefinitionSequence", [])
        labels = [getattr(ch, "ChannelLabel", f"ch{i}") for i, ch in enumerate(seq)]
        samples = np.frombuffer(item.WaveformData, dtype=np.int16)
        channels.append({
            "labels": labels,
            "sampling_frequency": float(getattr(item, "SamplingFrequency", 0)),
            "number_of_samples": int(getattr(item, "NumberOfWaveformSamples", 0)),
            # Only a small preview is stored in jsonb — full-resolution
            # waveform data belongs in object storage, not a DB column.
            "sample_preview": samples[:500].tolist(),
        })

    db.add(ReportExtraction(
        report_id=report.id,
        report_file_id=report_file.id,
        structured_data={"waveform_channels": channels},
        extraction_method="pydicom-waveform",
    ))
    db.commit()


def _dispatch(db, job: ProcessingJob, report: Report, report_file: ReportFile) -> None:
    if job.job_type == ProcessingJobType.normalization:
        # Checkpoint stage. Real cross-report normalization (unit
        # harmonization, de-duplicating repeated measurements across
        # visits) is meaningful future work, not implemented tonight.
        return

    raw_bytes = _download_original_bytes(report_file)

    if job.job_type == ProcessingJobType.virus_scan:
        _handle_virus_scan(db, report_file, raw_bytes, job)
    elif job.job_type == ProcessingJobType.ocr:
        _handle_ocr(db, report, report_file, raw_bytes)
    elif job.job_type == ProcessingJobType.table_extraction:
        _handle_table_extraction(db, report, report_file)
    elif job.job_type == ProcessingJobType.dicom_parsing:
        _handle_dicom_parsing(db, report, report_file, raw_bytes)
    elif job.job_type == ProcessingJobType.thumbnail_generation:
        _handle_thumbnail_generation(db, report_file, job)
    elif job.job_type == ProcessingJobType.structured_extraction:
        _handle_structured_extraction(db, report, report_file, raw_bytes)
    elif job.job_type == ProcessingJobType.waveform_processing:
        _handle_waveform(db, report, report_file, raw_bytes, job)
    else:
        raise NotImplementedError(f"No handler implemented for job_type={job.job_type}")


@celery_app.task(bind=True, name="process_report_job", max_retries=10)
def run_processing_job(self, job_id: str):
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job is None:
            return
        if job.status == ProcessingJobStatus.completed:
            return  # idempotency guard — a message got delivered twice

        job.status = ProcessingJobStatus.processing
        job.started_at = job.started_at or datetime.now(timezone.utc)
        db.commit()

        report_file = db.query(ReportFile).filter(ReportFile.id == job.report_file_id).first()
        report = db.query(Report).filter(Report.id == job.report_id).first()
        if report_file is None or report is None:
            job.status = ProcessingJobStatus.failed
            job.error_message = "report or report_file no longer exists"
            db.commit()
            return

        try:
            _dispatch(db, job, report, report_file)

        except QuarantineError as qe:
            job.status = ProcessingJobStatus.failed
            job.error_code = "malware_detected"
            job.error_message = str(qe)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            _cancel_remaining_jobs_for_file(db, report_file.id, reason="upstream file was quarantined")
            _maybe_finalize_report(db, report.id)
            return

        except Exception as exc:
            job.attempt += 1
            if job.attempt < job.max_attempts:
                job.status = ProcessingJobStatus.queued
                job.error_message = str(exc)[:500]
                db.commit()
                backoff_seconds = min(300, 2 ** job.attempt)
                raise self.retry(exc=exc, countdown=backoff_seconds)
            else:
                job.status = ProcessingJobStatus.failed
                job.error_code = "max_attempts_exceeded"
                job.error_message = str(exc)[:500]
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
                _cancel_remaining_jobs_for_file(db, report_file.id, reason="upstream stage failed permanently")
                _maybe_finalize_report(db, report.id)
                return

        job.status = ProcessingJobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        next_job_id = (job.metadata_json or {}).get("next_job_id")
        if next_job_id:
            next_job = db.query(ProcessingJob).filter(ProcessingJob.id == next_job_id).first()
            if next_job and next_job.job_type != ProcessingJobType.ai_analysis:
                run_processing_job.delay(str(next_job.id))
            # if the next stage IS ai_analysis, the chain deliberately stops here

        _maybe_finalize_report(db, report.id)
    finally:
        db.close()