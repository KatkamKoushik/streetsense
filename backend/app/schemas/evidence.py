from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    SENSOR_QUALITY_CHECK = "SENSOR_QUALITY_CHECK"
    KINETIC_JERK = "KINETIC_JERK"
    SUDDEN_DECELERATION = "SUDDEN_DECELERATION"
    PEDESTRIAN_FALL = "PEDESTRIAN_FALL"
    HIGH_SPEED_TRANSIT = "HIGH_SPEED_TRANSIT"
    ROAD_BOUNDARY_CROSSING = "ROAD_BOUNDARY_CROSSING"
    LOW_LIGHT_ENVIRONMENT = "LOW_LIGHT_ENVIRONMENT"
    GLARE_EXPOSURE = "GLARE_EXPOSURE"
    VISUAL_OBSTRUCTION = "VISUAL_OBSTRUCTION"
    APPROACHING_VEHICLE = "APPROACHING_VEHICLE"
    TEMPORAL_PERSISTENCE = "TEMPORAL_PERSISTENCE"
    SPATIAL_PROXIMITY = "SPATIAL_PROXIMITY"


class EvidenceItem(BaseModel):
    evidence_id: str
    expert_id: str
    evidence_type: EvidenceType
    confidence: float = Field(..., ge=0.0, le=1.0)
    timestamp_ns: int
    source_sensor: str
    attributes: Dict[str, Any] = Field(default_factory=dict)
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
