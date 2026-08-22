import enum
import uuid

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime, Enum, ForeignKey,
    Index, Integer, Numeric, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base
from app.models.health_records import TimestampMixin


class EquipmentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    under_maintenance = "under_maintenance"
    out_of_service = "out_of_service"
    retired = "retired"


class EquipmentCriticality(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EquipmentEventType(str, enum.Enum):
    usage_started = "usage_started"
    usage_stopped = "usage_stopped"
    breakdown = "breakdown"
    maintenance_started = "maintenance_started"
    maintenance_completed = "maintenance_completed"
    inspection = "inspection"
    status_changed = "status_changed"


class MaintenanceType(str, enum.Enum):
    preventive = "preventive"
    corrective = "corrective"
    emergency = "emergency"
    inspection = "inspection"


class ScarcityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class MedicalEquipment(Base, TimestampMixin):
    __tablename__ = "medical_equipment"
    __table_args__ = (UniqueConstraint("serial_number", name="uq_medical_equipment_serial_number"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id = Column(UUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="SET NULL"))
    name = Column(Text, nullable=False)
    equipment_type = Column(Text, nullable=False)
    manufacturer = Column(Text)
    model = Column(Text)
    serial_number = Column(Text)
    installation_date = Column(Date)
    status = Column(Enum(EquipmentStatus), nullable=False, default=EquipmentStatus.active)
    criticality = Column(Enum(EquipmentCriticality), nullable=False, default=EquipmentCriticality.medium)

    usage_sessions = relationship("EquipmentUsageSession", back_populates="equipment", cascade="all, delete-orphan")
    events = relationship("EquipmentEvent", back_populates="equipment", cascade="all, delete-orphan")
    maintenance_records = relationship("EquipmentMaintenance", back_populates="equipment", cascade="all, delete-orphan")
    components = relationship("EquipmentComponent", back_populates="equipment", cascade="all, delete-orphan")


class EquipmentUsageSession(Base):
    __tablename__ = "equipment_usage_sessions"
    __table_args__ = (
        CheckConstraint("ended_at is null or ended_at >= started_at", name="ck_usage_session_time_order"),
        CheckConstraint("duration_minutes is null or duration_minutes >= 0", name="ck_usage_session_duration_nonneg"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("medical_equipment.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Integer)
    recorded_by_name = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipment = relationship("MedicalEquipment", back_populates="usage_sessions")


class EquipmentEvent(Base):
    __tablename__ = "equipment_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("medical_equipment.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Enum(EquipmentEventType), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    description = Column(Text)
    recorded_by_name = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipment = relationship("MedicalEquipment", back_populates="events")


class EquipmentMaintenance(Base):
    __tablename__ = "equipment_maintenance"
    __table_args__ = (
        CheckConstraint("completed_at is null or completed_at >= started_at", name="ck_maintenance_time_order"),
        CheckConstraint("cost is null or cost >= 0", name="ck_maintenance_cost_nonneg"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("medical_equipment.id", ondelete="CASCADE"), nullable=False)
    maintenance_type = Column(Enum(MaintenanceType), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    description = Column(Text)
    technician_name = Column(Text)
    cost = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipment = relationship("MedicalEquipment", back_populates="maintenance_records")


class SemiconductorComponent(Base):
    __tablename__ = "semiconductor_components"
    __table_args__ = (
        UniqueConstraint("part_number", name="uq_semiconductor_components_part_number"),
        CheckConstraint("available_quantity >= 0", name="ck_component_available_nonneg"),
        CheckConstraint("reserved_quantity >= 0", name="ck_component_reserved_nonneg"),
        CheckConstraint("reorder_level >= 0", name="ck_component_reorder_nonneg"),
        CheckConstraint("lead_time_days >= 0", name="ck_component_lead_time_nonneg"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_name = Column(Text, nullable=False)
    part_number = Column(Text, nullable=False)
    manufacturer = Column(Text)
    category = Column(Text)
    available_quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)
    reorder_level = Column(Integer, nullable=False, default=0)
    lead_time_days = Column(Integer, nullable=False, default=0)
    scarcity_level = Column(Enum(ScarcityLevel), nullable=False, default=ScarcityLevel.low)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    equipment_links = relationship("EquipmentComponent", back_populates="component", cascade="all, delete-orphan")


class EquipmentComponent(Base):
    __tablename__ = "equipment_components"
    __table_args__ = (
        UniqueConstraint("equipment_id", "component_id", name="uq_equipment_component"),
        CheckConstraint("quantity_required > 0", name="ck_equipment_component_qty_positive"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("medical_equipment.id", ondelete="CASCADE"), nullable=False)
    component_id = Column(UUID(as_uuid=True), ForeignKey("semiconductor_components.id", ondelete="CASCADE"), nullable=False)
    quantity_required = Column(Integer, nullable=False, default=1)
    criticality = Column(Enum(EquipmentCriticality), nullable=False, default=EquipmentCriticality.medium)
    replacement_interval_days = Column(Integer)

    equipment = relationship("MedicalEquipment", back_populates="components")
    component = relationship("SemiconductorComponent", back_populates="equipment_links")


Index("idx_equipment_hospital", MedicalEquipment.hospital_id)
Index("idx_equipment_status", MedicalEquipment.status)
Index("idx_usage_sessions_equipment", EquipmentUsageSession.equipment_id)
Index("idx_usage_sessions_started_at", EquipmentUsageSession.started_at)
Index("idx_equipment_events_equipment", EquipmentEvent.equipment_id)
Index("idx_equipment_events_type", EquipmentEvent.event_type)
Index("idx_equipment_events_occurred_at", EquipmentEvent.occurred_at)
Index("idx_equipment_maintenance_equipment", EquipmentMaintenance.equipment_id)
Index("idx_equipment_maintenance_started_at", EquipmentMaintenance.started_at)
Index("idx_equipment_components_equipment", EquipmentComponent.equipment_id)
Index("idx_equipment_components_component", EquipmentComponent.component_id)
Index("idx_semiconductor_components_part_number", SemiconductorComponent.part_number)
Index("idx_semiconductor_components_scarcity", SemiconductorComponent.scarcity_level)