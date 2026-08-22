import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_role
from app.models.user import User
from app.schemas.equipment import (
    EquipmentComponentLink, EquipmentComponentOut, EquipmentEventCreate, EquipmentEventOut,
    EquipmentRiskOut, MaintenanceCreate, MaintenanceOut, MedicalEquipmentCreate,
    MedicalEquipmentOut, MedicalEquipmentUpdate, SemiconductorComponentCreate,
    SemiconductorComponentOut, UsageSessionOut, UsageSessionStart, UsageSessionStop,
)
from app.services import equipment_service
from app.services.equipment_risk import calculate_equipment_risk

router = APIRouter(prefix="/equipment", tags=["Equipment"])
components_router = APIRouter(prefix="/components", tags=["Components"])

# Read: doctor + hospital_admin + admin. Write: hospital_admin + admin (per your answer).
_WRITE_ROLES = ("hospital_admin", "admin")
_READ_ROLES = ("doctor", "hospital_admin", "admin")


@router.post("", response_model=MedicalEquipmentOut, status_code=201)
def create_equipment(payload: MedicalEquipmentCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.create_equipment(db, current_user, payload)


@router.get("", response_model=list[MedicalEquipmentOut])
def list_equipment(hospital_id: uuid.UUID | None = None, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_equipment(db, str(hospital_id) if hospital_id else None)


@router.get("/{equipment_id}", response_model=MedicalEquipmentOut)
def get_equipment(equipment_id: uuid.UUID, db: Session = Depends(get_db),
                   current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.get_equipment(db, equipment_id)


@router.patch("/{equipment_id}", response_model=MedicalEquipmentOut)
def update_equipment(equipment_id: uuid.UUID, payload: MedicalEquipmentUpdate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.update_equipment(db, current_user, equipment_id, payload)


@router.post("/{equipment_id}/usage-sessions/start", response_model=UsageSessionOut, status_code=201)
def start_usage_session(equipment_id: uuid.UUID, payload: UsageSessionStart, db: Session = Depends(get_db),
                         current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.start_usage_session(db, current_user, equipment_id, payload)


@router.post("/usage-sessions/{session_id}/stop", response_model=UsageSessionOut)
def stop_usage_session(session_id: uuid.UUID, payload: UsageSessionStop, db: Session = Depends(get_db),
                        current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.stop_usage_session(db, current_user, session_id, payload)


@router.get("/{equipment_id}/usage-sessions", response_model=list[UsageSessionOut])
def list_usage_sessions(equipment_id: uuid.UUID, db: Session = Depends(get_db),
                         current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_usage_sessions(db, equipment_id)


@router.post("/{equipment_id}/events", response_model=EquipmentEventOut, status_code=201)
def log_event(equipment_id: uuid.UUID, payload: EquipmentEventCreate, db: Session = Depends(get_db),
              current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.log_event(db, current_user, equipment_id, payload)


@router.get("/{equipment_id}/events", response_model=list[EquipmentEventOut])
def list_events(equipment_id: uuid.UUID, db: Session = Depends(get_db),
                 current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_events(db, equipment_id)


@router.post("/{equipment_id}/maintenance", response_model=MaintenanceOut, status_code=201)
def log_maintenance(equipment_id: uuid.UUID, payload: MaintenanceCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.log_maintenance(db, current_user, equipment_id, payload)


@router.get("/{equipment_id}/maintenance", response_model=list[MaintenanceOut])
def list_maintenance(equipment_id: uuid.UUID, db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_maintenance(db, equipment_id)


@router.post("/{equipment_id}/components", response_model=EquipmentComponentOut, status_code=201)
def link_component(equipment_id: uuid.UUID, payload: EquipmentComponentLink, db: Session = Depends(get_db),
                    current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.link_component(db, current_user, equipment_id, payload)


@router.get("/{equipment_id}/components", response_model=list[EquipmentComponentOut])
def list_equipment_components(equipment_id: uuid.UUID, db: Session = Depends(get_db),
                               current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_equipment_components(db, equipment_id)


@router.get("/{equipment_id}/risk", response_model=EquipmentRiskOut)
def get_equipment_risk(equipment_id: uuid.UUID, window_days: int = 30, db: Session = Depends(get_db),
                        current_user: User = Depends(require_role(*_READ_ROLES))):
    return calculate_equipment_risk(db, equipment_id, window_days=window_days)


@components_router.post("", response_model=SemiconductorComponentOut, status_code=201)
def create_component(payload: SemiconductorComponentCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(require_role(*_WRITE_ROLES))):
    return equipment_service.create_component(db, current_user, payload)


@components_router.get("", response_model=list[SemiconductorComponentOut])
def list_components(db: Session = Depends(get_db), current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_components(db)


@components_router.get("/{component_id}/equipment", response_model=list[EquipmentComponentOut])
def list_equipment_using_component(component_id: uuid.UUID, db: Session = Depends(get_db),
                                    current_user: User = Depends(require_role(*_READ_ROLES))):
    return equipment_service.list_equipment_using_component(db, component_id)