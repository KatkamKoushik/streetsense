from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from app.schemas.sensors import SensorSnapshot, LocationSnapshot
from app.schemas.experts import ExpertResult
from app.schemas.evidence import EvidenceItem
from app.schemas.events import DetectedEvent


class EventType(str, Enum):
    SESSION_STARTED = "session.started"
    SESSION_UPDATED = "session.updated"
    SENSOR_STATUS = "sensor.status"
    INFERENCE_STARTED = "inference.started"
    INFERENCE_COMPLETED = "inference.completed"
    EXPERT_STARTED = "expert.started"
    EXPERT_COMPLETED = "expert.completed"
    EXPERT_FAILED = "expert.failed"
    EVIDENCE_CREATED = "evidence.created"
    EVENT_DETECTED = "event.detected"
    EVENT_UPDATED = "event.updated"
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_DISMISSED = "alert.dismissed"
    DEVICE_STATUS = "device.status"
    CONNECTION_STATUS = "connection.status"
    HEARTBEAT_PING = "heartbeat.ping"
    HEARTBEAT_PONG = "heartbeat.pong"


class DeviceStatusPayload(BaseModel):
    battery_level: float = Field(..., ge=0.0, le=100.0)
    battery_temperature_c: float
    is_charging: bool
    thermal_state: str = "NORMAL"  # NORMAL, LIGHT, MODERATE, SEVERE, CRITICAL
    network_type: str = "WIFI"  # WIFI, CELLULAR, OFFLINE
    active_sensors: List[str] = Field(default_factory=list)
    degraded_sensors: List[str] = Field(default_factory=list)


class TelemetryIngressPayload(BaseModel):
    snapshots: List[SensorSnapshot] = Field(default_factory=list)
    location: Optional[LocationSnapshot] = None
    expert_results: List[ExpertResult] = Field(default_factory=list)
    evidences: List[EvidenceItem] = Field(default_factory=list)
    events: List[DetectedEvent] = Field(default_factory=list)
    device_status: Optional[DeviceStatusPayload] = None


class WsMessageEnvelope(BaseModel):
    message_id: str
    correlation_id: str
    session_id: str
    device_id: str
    timestamp_ns: int
    event_type: EventType
    sequence_number: int = Field(..., ge=0)
    payload: Dict[str, Any] = Field(default_factory=dict)
