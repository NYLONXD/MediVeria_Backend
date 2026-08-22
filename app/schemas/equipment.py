import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.equipment import (
    EquipmentCriticality,
    EquipmentEventType,
    EquipmentStatus,
    MaintenanceType,
    ScarcityLevel,
)


class MedicalEquipmentCreate(BaseModel):
    hospital_id: Optional[uuid.UUID] = None
    name: str
    equipment_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    status: EquipmentStatus = EquipmentStatus.active
    criticality: EquipmentCriticality = EquipmentCriticality.medium


class MedicalEquipmentUpdate(BaseModel):
    name: Optional[str] = None
    equipment_type: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    status: Optional[EquipmentStatus] = None
    criticality: Optional[EquipmentCriticality] = None


class MedicalEquipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hospital_id: Optional[uuid.UUID] = None
    name: str
    equipment_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    installation_date: Optional[date] = None
    status: EquipmentStatus
    criticality: EquipmentCriticality
    created_at: datetime
    updated_at: datetime


class UsageSessionStart(BaseModel):
    started_at: Optional[datetime] = None
    recorded_by_name: Optional[str] = None


class UsageSessionStop(BaseModel):
    ended_at: Optional[datetime] = None


class UsageSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_id: uuid.UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    recorded_by_name: Optional[str] = None
    created_at: datetime


class EquipmentEventCreate(BaseModel):
    event_type: EquipmentEventType
    occurred_at: Optional[datetime] = None
    description: Optional[str] = None
    recorded_by_name: Optional[str] = None


class EquipmentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_id: uuid.UUID
    event_type: EquipmentEventType
    occurred_at: datetime
    description: Optional[str] = None
    recorded_by_name: Optional[str] = None


class MaintenanceCreate(BaseModel):
    maintenance_type: MaintenanceType
    started_at: datetime
    completed_at: Optional[datetime] = None
    description: Optional[str] = None
    technician_name: Optional[str] = None
    cost: Optional[float] = None


class MaintenanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_id: uuid.UUID
    maintenance_type: MaintenanceType
    started_at: datetime
    completed_at: Optional[datetime] = None
    description: Optional[str] = None
    technician_name: Optional[str] = None
    cost: Optional[float] = None


class SemiconductorComponentCreate(BaseModel):
    component_name: str
    part_number: str
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    available_quantity: int = 0
    reserved_quantity: int = 0
    reorder_level: int = 0
    lead_time_days: int = 0
    scarcity_level: ScarcityLevel = ScarcityLevel.low


class SemiconductorComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    component_name: str
    part_number: str
    manufacturer: Optional[str] = None
    category: Optional[str] = None
    available_quantity: int
    reserved_quantity: int
    reorder_level: int
    lead_time_days: int
    scarcity_level: ScarcityLevel


class EquipmentComponentLink(BaseModel):
    component_id: uuid.UUID
    quantity_required: int = 1
    criticality: EquipmentCriticality = EquipmentCriticality.medium
    replacement_interval_days: Optional[int] = None


class EquipmentComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_id: uuid.UUID
    component_id: uuid.UUID
    quantity_required: int
    criticality: EquipmentCriticality
    replacement_interval_days: Optional[int] = None


class EquipmentRiskOut(BaseModel):
    equipment_id: uuid.UUID
    utilization_score: float
    failure_score: float
    downtime_score: float
    maintenance_score: float
    scarcity_score: float
    criticality_score: float
    risk_score: float
    risk_level: str
    window_days: int