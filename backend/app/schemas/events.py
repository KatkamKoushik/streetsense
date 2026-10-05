from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.evidence import EvidenceItem


class EventSeverity(str, Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL = "CRITICAL"


class EventCategory(str, Enum):
    PEDESTRIAN_FALL_OR_IMPACT = "PEDESTRIAN_FALL_OR_IMPACT"
    VEHICLE_APPROACH_COLLISION = "VEHICLE_APPROACH_COLLISION"
    ROAD_HAZARD_OBSTRUCTION = "ROAD_HAZARD_OBSTRUCTION"
    POOR_VISIBILITY_HAZARD = "POOR_VISIBILITY_HAZARD"
    ANOMALOUS_MOTION = "ANOMALOUS_MOTION"
    SENSOR_MALFUNCTION = "SENSOR_MALFUNCTION"


class ConfidenceBreakdown(BaseModel):
    prediction_confidence: float = Field(..., ge=0.0, le=1.0)
    input_quality: float = Field(..., ge=0.0, le=1.0)
    temporal_consistency: float = Field(..., ge=0.0, le=1.0)
    sensor_reliability: float = Field(..., ge=0.0, le=1.0)
    cross_expert_agreement: float = Field(..., ge=0.0, le=1.0)
    geometric_consistency: float = Field(..., ge=0.0, le=1.0)
    evidence_quality: float = Field(..., ge=0.0, le=1.0)
    final_decision_confidence: float = Field(..., ge=0.0, le=1.0)


class DetectedEvent(BaseModel):
    event_id: str
    session_id: str
    timestamp_ns: int
    category: EventCategory
    severity: EventSeverity
    confidence_breakdown: ConfidenceBreakdown
    contributing_evidence_ids: List[str] = Field(default_factory=list)
    contributing_evidence: List[EvidenceItem] = Field(default_factory=list)
    explanation: str = Field(..., description="Grounded, evidence-cited human readable explanation")
    haptic_pattern: str = "PULSE_ALERT"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_dismissed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
