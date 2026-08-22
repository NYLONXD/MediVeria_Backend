from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.equipment import (
    EquipmentComponent,
    EquipmentEvent,
    EquipmentMaintenance,
    EquipmentUsageSession,
    MedicalEquipment,
    SemiconductorComponent,
)
from app.models.health_records import AuditAction, AuditLog
from app.models.user import User
from app.schemas.equipment import (
    EquipmentComponentLink,
    EquipmentEventCreate,
    MaintenanceCreate,
    MedicalEquipmentCreate,
    MedicalEquipmentUpdate,
    SemiconductorComponentCreate,
    UsageSessionStart,
    UsageSessionStop,
)


def _get_equipment_or_404(db: Session, equipment_id) -> MedicalEquipment:
    equipment = db.query(MedicalEquipment).filter(MedicalEquipment.id == equipment_id).first()
    if not equipment:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return equipment


# ---- equipment registry ----

def create_equipment(db: Session, current_user: User, payload: MedicalEquipmentCreate) -> MedicalEquipment:
    equipment = MedicalEquipment(**payload.model_dump())
    db.add(equipment)
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_create, entity_type="medical_equipment", entity_id=equipment.id))
    db.commit()
    db.refresh(equipment)
    return equipment


def update_equipment(db: Session, current_user: User, equipment_id, payload: MedicalEquipmentUpdate) -> MedicalEquipment:
    equipment = _get_equipment_or_404(db, equipment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(equipment, field, value)
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_update, entity_type="medical_equipment", entity_id=equipment.id))
    db.commit()
    db.refresh(equipment)
    return equipment


def list_equipment(db: Session, hospital_id: Optional[str] = None) -> list[MedicalEquipment]:
    query = db.query(MedicalEquipment)
    if hospital_id:
        query = query.filter(MedicalEquipment.hospital_id == hospital_id)
    return query.order_by(MedicalEquipment.name).all()


def get_equipment(db: Session, equipment_id) -> MedicalEquipment:
    return _get_equipment_or_404(db, equipment_id)


# ---- usage sessions ----

def start_usage_session(db: Session, current_user: User, equipment_id, payload: UsageSessionStart) -> EquipmentUsageSession:
    _get_equipment_or_404(db, equipment_id)
    open_session = (
        db.query(EquipmentUsageSession)
        .filter(EquipmentUsageSession.equipment_id == equipment_id, EquipmentUsageSession.ended_at.is_(None))
        .first()
    )
    if open_session:
        raise HTTPException(status_code=400, detail="Equipment already has an open usage session")

    session = EquipmentUsageSession(
        equipment_id=equipment_id,
        started_at=payload.started_at or datetime.now(timezone.utc),
        recorded_by_name=payload.recorded_by_name,
    )
    db.add(session)
    db.flush()
    db.add(EquipmentEvent(equipment_id=equipment_id, event_type="usage_started", occurred_at=session.started_at, recorded_by_name=payload.recorded_by_name))
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_usage_log, entity_type="equipment_usage_sessions", entity_id=session.id))
    db.commit()
    db.refresh(session)
    return session


def stop_usage_session(db: Session, current_user: User, session_id, payload: UsageSessionStop) -> EquipmentUsageSession:
    session = db.query(EquipmentUsageSession).filter(EquipmentUsageSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Usage session not found")
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Usage session already stopped")

    ended_at = payload.ended_at or datetime.now(timezone.utc)
    if ended_at < session.started_at:
        raise HTTPException(status_code=400, detail="ended_at cannot be before started_at")

    session.ended_at = ended_at
    session.duration_minutes = int((ended_at - session.started_at).total_seconds() // 60)
    db.add(EquipmentEvent(equipment_id=session.equipment_id, event_type="usage_stopped", occurred_at=ended_at))
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_usage_log, entity_type="equipment_usage_sessions", entity_id=session.id))
    db.commit()
    db.refresh(session)
    return session


def list_usage_sessions(db: Session, equipment_id) -> list[EquipmentUsageSession]:
    return (
        db.query(EquipmentUsageSession)
        .filter(EquipmentUsageSession.equipment_id == equipment_id)
        .order_by(EquipmentUsageSession.started_at.desc())
        .all()
    )


# ---- events ----

def log_event(db: Session, current_user: User, equipment_id, payload: EquipmentEventCreate) -> EquipmentEvent:
    _get_equipment_or_404(db, equipment_id)
    event = EquipmentEvent(
        equipment_id=equipment_id,
        event_type=payload.event_type,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        description=payload.description,
        recorded_by_name=payload.recorded_by_name,
    )
    db.add(event)
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_event_log, entity_type="equipment_events", entity_id=event.id))
    db.commit()
    db.refresh(event)
    return event


def list_events(db: Session, equipment_id) -> list[EquipmentEvent]:
    return (
        db.query(EquipmentEvent)
        .filter(EquipmentEvent.equipment_id == equipment_id)
        .order_by(EquipmentEvent.occurred_at.desc())
        .all()
    )


# ---- maintenance ----

def log_maintenance(db: Session, current_user: User, equipment_id, payload: MaintenanceCreate) -> EquipmentMaintenance:
    _get_equipment_or_404(db, equipment_id)
    record = EquipmentMaintenance(equipment_id=equipment_id, **payload.model_dump())
    db.add(record)
    db.flush()
    event_type = "maintenance_completed" if record.completed_at else "maintenance_started"
    db.add(EquipmentEvent(equipment_id=equipment_id, event_type=event_type, occurred_at=record.completed_at or record.started_at, recorded_by_name=record.technician_name))
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.equipment_maintenance_log, entity_type="equipment_maintenance", entity_id=record.id))
    db.commit()
    db.refresh(record)
    return record


def list_maintenance(db: Session, equipment_id) -> list[EquipmentMaintenance]:
    return (
        db.query(EquipmentMaintenance)
        .filter(EquipmentMaintenance.equipment_id == equipment_id)
        .order_by(EquipmentMaintenance.started_at.desc())
        .all()
    )


# ---- semiconductor components ----

def create_component(db: Session, current_user: User, payload: SemiconductorComponentCreate) -> SemiconductorComponent:
    component = SemiconductorComponent(**payload.model_dump())
    db.add(component)
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action=AuditAction.component_inventory_update, entity_type="semiconductor_components", entity_id=component.id))
    db.commit()
    db.refresh(component)
    return component


def list_components(db: Session) -> list[SemiconductorComponent]:
    return db.query(SemiconductorComponent).order_by(SemiconductorComponent.component_name).all()


def link_component(db: Session, current_user: User, equipment_id, payload: EquipmentComponentLink) -> EquipmentComponent:
    _get_equipment_or_404(db, equipment_id)
    component = db.query(SemiconductorComponent).filter(SemiconductorComponent.id == payload.component_id).first()
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")

    link = EquipmentComponent(equipment_id=equipment_id, **payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_equipment_components(db: Session, equipment_id) -> list[EquipmentComponent]:
    return (
        db.query(EquipmentComponent)
        .options(joinedload(EquipmentComponent.component))
        .filter(EquipmentComponent.equipment_id == equipment_id)
        .all()
    )


def list_equipment_using_component(db: Session, component_id) -> list[EquipmentComponent]:
    return (
        db.query(EquipmentComponent)
        .options(joinedload(EquipmentComponent.equipment))
        .filter(EquipmentComponent.component_id == component_id)
        .all()
    )