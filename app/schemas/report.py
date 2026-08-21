import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.health_records import PipelineStage, ProcessingJobStatus, ProcessingJobType, ReportStatus, ReportType, SourceFormat


class PendingPatientCreate(BaseModel):
    full_name: str
    phone: str
    dob: date
    hospital_id: Optional[uuid.UUID] = None


class ReportCreate(BaseModel):
    patient_id: Optional[uuid.UUID] = None
    pending_patient: Optional[PendingPatientCreate] = None
    hospital_id: Optional[uuid.UUID] = None
    report_type: ReportType
    title: str
    description: Optional[str] = None
    report_date: Optional[date] = None
    issued_by_name: Optional[str] = None
    issued_by_department: Optional[str] = None


class ReportFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_format: SourceFormat
    bucket_name: str
    object_key: str
    mime_type: Optional[str] = None
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    is_encrypted: bool
    is_quarantined: bool = False
    created_at: datetime
    view_url: Optional[str] = None  # signed Cloudinary URL, generated on read — not persisted


class ProcessingJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_file_id: Optional[uuid.UUID] = None
    job_type: ProcessingJobType
    status: ProcessingJobStatus
    stage: Optional[PipelineStage] = None
    attempt: int
    max_attempts: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ReportExtractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_file_id: Optional[uuid.UUID] = None
    extracted_text: Optional[str] = None
    structured_data: Optional[dict] = None
    extraction_method: Optional[str] = None
    created_at: datetime


class ReportMeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_name: str
    value_numeric: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    reference_min: Optional[float] = None
    reference_max: Optional[float] = None
    abnormal_flag: Optional[str] = None


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: Optional[uuid.UUID] = None
    pending_patient_id: Optional[uuid.UUID] = None
    uploaded_by_doctor_id: Optional[uuid.UUID] = None
    hospital_id: Optional[uuid.UUID] = None
    report_type: ReportType
    title: str
    description: Optional[str] = None
    report_date: Optional[date] = None
    status: ReportStatus
    pipeline_stage: PipelineStage
    issued_by_name: Optional[str] = None
    issued_by_department: Optional[str] = None
    uploaded_at: datetime
    files: list[ReportFileOut] = Field(default_factory=list)
    processing_jobs: list[ProcessingJobOut] = Field(default_factory=list)
    extractions: list[ReportExtractionOut] = Field(default_factory=list)
    measurements: list[ReportMeasurementOut] = Field(default_factory=list)