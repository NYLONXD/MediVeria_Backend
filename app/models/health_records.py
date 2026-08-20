import enum
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ReportType(str, enum.Enum):
    mri = "mri"
    ct_scan = "ct_scan"
    xray = "xray"
    ultrasound = "ultrasound"
    blood_test = "blood_test"
    lab_report = "lab_report"
    ecg = "ecg"
    prescription = "prescription"
    discharge_summary = "discharge_summary"
    doctor_notes = "doctor_notes"
    pathology = "pathology"
    biopsy = "biopsy"
    vaccination = "vaccination"
    medical_certificate = "medical_certificate"
    other = "other"


class ReportStatus(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"
    archived = "archived"


class SourceFormat(str, enum.Enum):
    pdf = "pdf"
    image = "image"
    dicom = "dicom"
    structured = "structured"


class FileRole(str, enum.Enum):
    original = "original"
    attachment = "attachment"
    derived = "derived"
    thumbnail = "thumbnail"


class ClaimStatus(str, enum.Enum):
    pending = "pending"
    claimed = "claimed"
    expired = "expired"
    revoked = "revoked"


class ProcessingJobType(str, enum.Enum):
    virus_scan = "virus_scan"
    text_extraction = "text_extraction"
    ocr = "ocr"
    table_extraction = "table_extraction"
    structured_extraction = "structured_extraction"
    dicom_parsing = "dicom_parsing"
    waveform_processing = "waveform_processing"
    normalization = "normalization"
    thumbnail_generation = "thumbnail_generation"
    ai_analysis = "ai_analysis"


class ProcessingJobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PipelineStage(str, enum.Enum):
    uploaded = "uploaded"
    scanning = "scanning"
    extracting = "extracting"
    extracted = "extracted"
    structuring = "structuring"
    analyzing = "analyzing"
    completed = "completed"
    failed = "failed"


class AccessPermission(str, enum.Enum):
    view = "view"
    download = "download"
    upload = "upload"
    share = "share"


class AppointmentStatus(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class AppointmentType(str, enum.Enum):
    in_person = "in_person"
    telemedicine = "telemedicine"


class NotificationType(str, enum.Enum):
    report_ready = "report_ready"
    appointment = "appointment"
    chat_message = "chat_message"
    system = "system"
    claim = "claim"


class AiAnalysisType(str, enum.Enum):
    patient_explanation = "patient_explanation"
    doctor_summary = "doctor_summary"
    risk_summary = "risk_summary"


class AuditAction(str, enum.Enum):
    login = "login"
    logout = "logout"
    report_upload = "report_upload"
    report_view = "report_view"
    report_download = "report_download"
    report_share = "report_share"
    report_delete = "report_delete"
    report_claim = "report_claim"
    report_analyze = "report_analyze"
    appointment_create = "appointment_create"
    appointment_update = "appointment_update"
    chat_send = "chat_send"
    profile_update = "profile_update"
    access_granted = "access_granted"
    access_revoked = "access_revoked"
    other = "other"


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Hospital(Base, TimestampMixin):
    __tablename__ = "hospitals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    registration_no = Column(Text, unique=True)
    address = Column(Text)
    city = Column(Text)
    phone = Column(Text)
    email = Column(Text)
    is_verified = Column(Boolean, nullable=False, default=False)


class Doctor(Base, TimestampMixin):
    __tablename__ = "doctors"

    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"))
    license_number = Column(Text, unique=True, nullable=False)
    specialization = Column(Text)
    years_experience = Column(Integer, CheckConstraint("years_experience >= 0"))
    bio = Column(Text)
    consultation_fee = Column(Numeric(10, 2), CheckConstraint("consultation_fee >= 0"))
    is_verified = Column(Boolean, nullable=False, default=False)


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    date_of_birth = Column(Date)
    blood_group = Column(Text)
    height_cm = Column(Numeric(5, 2), CheckConstraint("height_cm > 0"))
    weight_kg = Column(Numeric(5, 2), CheckConstraint("weight_kg > 0"))
    emergency_contact_name = Column(Text)
    emergency_contact_phone = Column(Text)
    allergies = Column(ARRAY(Text))
    chronic_conditions = Column(ARRAY(Text))


class PendingPatient(Base):
    __tablename__ = "pending_patients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(Text, nullable=False)
    phone = Column(Text, nullable=False)
    dob = Column(Date, nullable=False)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"))
    created_by_doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"))
    claim_id = Column(Text, unique=True, nullable=False)
    status = Column(Enum(ClaimStatus), nullable=False, default=ClaimStatus.pending)
    claimed_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    claimed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True))


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "(patient_id is not null and pending_patient_id is null) or "
            "(patient_id is null and pending_patient_id is not null)",
            name="ck_reports_exactly_one_owner",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"))
    pending_patient_id = Column(UUID(as_uuid=True), ForeignKey("pending_patients.id", ondelete="RESTRICT"))
    uploaded_by_doctor_id = Column(UUID(as_uuid=True), ForeignKey("doctors.id", ondelete="SET NULL"))
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"))
    report_type = Column(Enum(ReportType), nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    report_date = Column(Date)
    status = Column(Enum(ReportStatus), nullable=False, default=ReportStatus.processing)
    pipeline_stage = Column(Enum(PipelineStage), nullable=False, default=PipelineStage.uploaded)
    issued_by_name = Column(Text)
    issued_by_department = Column(Text)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    files = relationship("ReportFile", back_populates="report", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="report", cascade="all, delete-orphan")


class ReportFile(Base):
    __tablename__ = "report_files"
    __table_args__ = (UniqueConstraint("bucket_name", "object_key", name="uq_report_files_bucket_object"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_file_id = Column(UUID(as_uuid=True), ForeignKey("report_files.id", ondelete="SET NULL"))
    source_format = Column(Enum(SourceFormat), nullable=False)
    role = Column(Enum(FileRole), nullable=False, default=FileRole.original)
    bucket_name = Column(Text, nullable=False)
    object_key = Column(Text, nullable=False)
    mime_type = Column(Text)
    file_name = Column(Text)
    file_size_bytes = Column(BigInteger, CheckConstraint("file_size_bytes >= 0"))
    checksum_sha256 = Column(Text)
    encryption_key_ref = Column(Text)
    is_encrypted = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    report = relationship("Report", back_populates="files")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    report_file_id = Column(UUID(as_uuid=True), ForeignKey("report_files.id", ondelete="CASCADE"))
    job_type = Column(Enum(ProcessingJobType), nullable=False)
    status = Column(Enum(ProcessingJobStatus), nullable=False, default=ProcessingJobStatus.queued)
    stage = Column(Enum(PipelineStage))
    attempt = Column(Integer, CheckConstraint("attempt >= 0"), nullable=False, default=0)
    max_attempts = Column(Integer, CheckConstraint("max_attempts > 0"), nullable=False, default=3)
    error_code = Column(Text)
    error_message = Column(Text)
    worker_id = Column(Text)
    metadata_json = Column("metadata", JSONB)
    queued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    report = relationship("Report", back_populates="processing_jobs")


class ReportExtraction(Base):
    __tablename__ = "report_extractions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    report_file_id = Column(UUID(as_uuid=True), ForeignKey("report_files.id", ondelete="SET NULL"))
    extracted_text = Column(Text)
    structured_data = Column(JSONB)
    extraction_method = Column(Text)
    language = Column(Text)
    confidence_score = Column(Numeric(4, 3), CheckConstraint("confidence_score is null or (confidence_score >= 0 and confidence_score <= 1)"))
    parser_version = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ReportMeasurement(Base):
    __tablename__ = "report_measurements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("report_extractions.id", ondelete="SET NULL"))
    test_name = Column(Text, nullable=False)
    value_numeric = Column(Numeric)
    value_text = Column(Text)
    unit = Column(Text)
    reference_min = Column(Numeric)
    reference_max = Column(Numeric)
    abnormal_flag = Column(Text)
    measured_at = Column(DateTime(timezone=True))
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AiAnalysis(Base):
    __tablename__ = "ai_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    extraction_id = Column(UUID(as_uuid=True), ForeignKey("report_extractions.id", ondelete="SET NULL"))
    analysis_type = Column(Enum(AiAnalysisType), nullable=False)
    summary = Column(Text)
    simplified_explanation = Column(Text)
    risk_indicators = Column(JSONB)
    recommendations = Column(JSONB)
    confidence_score = Column(Numeric(4, 3), CheckConstraint("confidence_score is null or (confidence_score >= 0 and confidence_score <= 1)"))
    model_name = Column(Text)
    model_version = Column(Text)
    prompt_version = Column(Text)
    safety_disclaimer = Column(Text)
    status = Column(Enum(ProcessingJobStatus), default=ProcessingJobStatus.queued)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(Enum(AuditAction), nullable=False)
    entity_type = Column(Text)
    entity_id = Column(UUID(as_uuid=True))
    ip_address = Column(INET)
    user_agent = Column(Text)
    request_id = Column(Text)
    success = Column(Boolean, nullable=False, default=True)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("idx_reports_patient", Report.patient_id)
Index("idx_reports_pending_patient", Report.pending_patient_id)
Index("idx_reports_doctor", Report.uploaded_by_doctor_id)
Index("idx_reports_hospital", Report.hospital_id)
Index("idx_reports_date", Report.report_date.desc())
Index("idx_processing_jobs_report", ProcessingJob.report_id)
Index("idx_processing_jobs_status", ProcessingJob.status)
Index("idx_report_extractions_report", ReportExtraction.report_id)
Index("idx_measurements_report", ReportMeasurement.report_id)
Index("idx_ai_analysis_report", AiAnalysis.report_id)
Index("idx_audit_logs_user", AuditLog.user_id)
Index("idx_audit_logs_entity", AuditLog.entity_type, AuditLog.entity_id)
Index("idx_audit_logs_created", AuditLog.created_at.desc())
