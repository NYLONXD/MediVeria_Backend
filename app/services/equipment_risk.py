"""
Transparent, rule-based equipment risk score. Six normalized (0-100)
sub-scores combined with fixed weights — no ML. Weights and thresholds
are application-defined constants for this MVP, not medical/regulatory
standards.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.equipment import (
    EquipmentComponent,
    EquipmentCriticality,
    EquipmentEvent,
    EquipmentEventType,
    EquipmentMaintenance,
    EquipmentUsageSession,
    MedicalEquipment,
    ScarcityLevel,
)
from app.schemas.equipment import EquipmentRiskOut

WEIGHTS = {
    "utilization": 0.25,
    "failure": 0.20,
    "downtime": 0.15,
    "maintenance": 0.15,
    "scarcity": 0.15,
    "criticality": 0.10,
}

FAILURE_SCORE_CAP = 10          # breakdown count in-window that maps to failure_score=100
MAINTENANCE_TARGET_DAYS = 90    # "on schedule" preventive interval

_SCARCITY_BASE = {ScarcityLevel.low: 25, ScarcityLevel.medium: 50, ScarcityLevel.high: 75, ScarcityLevel.critical: 100}
_CRITICALITY_BASE = {EquipmentCriticality.low: 25, EquipmentCriticality.medium: 50, EquipmentCriticality.high: 75, EquipmentCriticality.critical: 100}


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def calculate_equipment_risk(
    db: Session,
    equipment_id,
    window_days: int = 30,
    operating_hours_per_day: float = 24.0,
) -> EquipmentRiskOut:
    equipment = db.query(MedicalEquipment).filter(MedicalEquipment.id == equipment_id).first()
    if equipment is None:
        raise ValueError("Equipment not found")

    window_start = datetime.now(timezone.utc) - timedelta(days=window_days)
    available_hours = operating_hours_per_day * window_days

    sessions = (
        db.query(EquipmentUsageSession)
        .filter(EquipmentUsageSession.equipment_id == equipment_id, EquipmentUsageSession.started_at >= window_start)
        .all()
    )
    operating_hours = sum(s.duration_minutes or 0 for s in sessions) / 60
    utilization_score = _clamp((operating_hours / available_hours) * 100) if available_hours else 0

    breakdown_count = (
        db.query(EquipmentEvent)
        .filter(
            EquipmentEvent.equipment_id == equipment_id,
            EquipmentEvent.event_type == EquipmentEventType.breakdown,
            EquipmentEvent.occurred_at >= window_start,
        )
        .count()
    )
    failure_score = _clamp((breakdown_count / FAILURE_SCORE_CAP) * 100)

    maintenance_records = (
        db.query(EquipmentMaintenance)
        .filter(EquipmentMaintenance.equipment_id == equipment_id, EquipmentMaintenance.started_at >= window_start)
        .all()
    )
    downtime_minutes = sum(
        max(((m.completed_at or datetime.now(timezone.utc)) - m.started_at).total_seconds() / 60, 0)
        for m in maintenance_records
    )
    downtime_hours = downtime_minutes / 60
    downtime_score = _clamp((downtime_hours / available_hours) * 100) if available_hours else 0

    last_completed = (
        db.query(EquipmentMaintenance)
        .filter(EquipmentMaintenance.equipment_id == equipment_id, EquipmentMaintenance.completed_at.isnot(None))
        .order_by(EquipmentMaintenance.completed_at.desc())
        .first()
    )
    reference_date = last_completed.completed_at if last_completed else equipment.created_at
    days_since = max((datetime.now(timezone.utc) - reference_date).days, 0)
    maintenance_score = _clamp((days_since / MAINTENANCE_TARGET_DAYS) * 100)

    links = db.query(EquipmentComponent).filter(EquipmentComponent.equipment_id == equipment_id).all()
    scarcity_score = 0.0
    for link in links:
        component = link.component
        base = _SCARCITY_BASE[component.scarcity_level]
        if component.available_quantity <= component.reorder_level:
            base = min(base + 15, 100)
        scarcity_score = max(scarcity_score, base)

    criticality_score = _CRITICALITY_BASE[equipment.criticality]

    risk_score = _clamp(
        WEIGHTS["utilization"] * utilization_score
        + WEIGHTS["failure"] * failure_score
        + WEIGHTS["downtime"] * downtime_score
        + WEIGHTS["maintenance"] * maintenance_score
        + WEIGHTS["scarcity"] * scarcity_score
        + WEIGHTS["criticality"] * criticality_score
    )

    if risk_score <= 30:
        risk_level = "LOW"
    elif risk_score <= 60:
        risk_level = "MEDIUM"
    elif risk_score <= 80:
        risk_level = "HIGH"
    else:
        risk_level = "CRITICAL"

    return EquipmentRiskOut(
        equipment_id=equipment_id,
        utilization_score=round(utilization_score, 1),
        failure_score=round(failure_score, 1),
        downtime_score=round(downtime_score, 1),
        maintenance_score=round(maintenance_score, 1),
        scarcity_score=round(scarcity_score, 1),
        criticality_score=round(criticality_score, 1),
        risk_score=round(risk_score, 1),
        risk_level=risk_level,
        window_days=window_days,
    )