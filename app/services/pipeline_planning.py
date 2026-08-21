"""
Single source of truth for what pipeline a given report file goes through.

report_service.py uses this to create the ProcessingJob rows in the right
order at upload time. workers/tasks.py trusts job_type on each row to know
what to actually run — this module is what defines that order in the first
place, so the two never drift apart.
"""

from app.models.health_records import PipelineStage, ProcessingJobType, ReportType, SourceFormat


def detect_source_format(content_type: str | None, filename: str | None) -> SourceFormat:
    value = (content_type or filename or "").lower()
    if "pdf" in value or value.endswith(".pdf"):
        return SourceFormat.pdf
    if "dicom" in value or value.endswith((".dcm", ".dicom")):
        return SourceFormat.dicom
    if "image" in value or value.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceFormat.image
    return SourceFormat.structured


def plan_jobs(report_type: ReportType, source_format: SourceFormat) -> list[tuple[ProcessingJobType, PipelineStage]]:
    jobs: list[tuple[ProcessingJobType, PipelineStage]] = [(ProcessingJobType.virus_scan, PipelineStage.scanning)]

    if source_format == SourceFormat.dicom:
        jobs += [
            (ProcessingJobType.dicom_parsing, PipelineStage.extracting),
            (ProcessingJobType.thumbnail_generation, PipelineStage.extracting),
        ]
    elif source_format in {SourceFormat.pdf, SourceFormat.image}:
        # ocr MUST come before table_extraction — table_extraction parses
        # the text ocr just produced. (This was reversed in an earlier
        # draft — reordering it here was the actual bug fix.)
        jobs.append((ProcessingJobType.ocr, PipelineStage.extracting))
        if report_type.value in {"blood_test", "lab_report"}:
            jobs.append((ProcessingJobType.table_extraction, PipelineStage.extracting))
    else:
        jobs.append((ProcessingJobType.structured_extraction, PipelineStage.extracting))

    if report_type.value == "ecg":
        jobs.append((ProcessingJobType.waveform_processing, PipelineStage.extracting))

    jobs += [
        (ProcessingJobType.normalization, PipelineStage.structuring),
        # ai_analysis is planned but never enqueued by the worker chain —
        # AI is intentionally out of scope right now. The row exists so the
        # frontend can show "AI analysis: not started" honestly instead of
        # the stage not existing at all.
        (ProcessingJobType.ai_analysis, PipelineStage.analyzing),
    ]
    return jobs