from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.sensors import SensorSnapshot, FrameMetadata, LocationSnapshot


class ExpertCapability(str, Enum):
    SENSOR_QUALITY = "SENSOR_QUALITY"
    MOTION_ANALYSIS = "MOTION_ANALYSIS"
    LOCATION_ANALYSIS = "LOCATION_ANALYSIS"
    OBJECT_DETECTION = "OBJECT_DETECTION"
    SCENE_ANALYSIS = "SCENE_ANALYSIS"
    ROAD_ANALYSIS = "ROAD_ANALYSIS"
    TEMPORAL_CHANGE = "TEMPORAL_CHANGE"
    ILLUMINATION_ANALYSIS = "ILLUMINATION_ANALYSIS"
    HAZARD_ANALYSIS = "HAZARD_ANALYSIS"
    SPATIAL_CONTEXT = "SPATIAL_CONTEXT"
    EVIDENCE_FUSION = "EVIDENCE_FUSION"
    ARBITRATION = "ARBITRATION"
    REASONING = "REASONING"


class ExecutionStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    SELECTED = "SELECTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ModelProvenance(BaseModel):
    runtime: str = Field(..., description="e.g. tflite, onnx-mobile, deterministic-heuristic, local-llm")
    model_name: str
    version: str
    quantization: Optional[str] = None  # e.g. int8, fp16, none
    device: str = "cpu"  # cpu, gpu, npu, dsp
    sha256: Optional[str] = None


class ExpertRequest(BaseModel):
    session_id: str
    correlation_id: str
    target_capabilities: List[ExpertCapability]
    sensor_snapshots: List[SensorSnapshot] = Field(default_factory=list)
    frame_metadata: Optional[FrameMetadata] = None
    location_snapshot: Optional[LocationSnapshot] = None
    budget_ms: float = 50.0
    energy_constraint: str = "NORMAL"  # LOW_BATTERY, THERMAL_THROTTLED, NORMAL


class ExpertResult(BaseModel):
    expert_id: str
    capability: ExpertCapability
    status: ExecutionStatus
    prediction: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    timestamp_ns: int
    provenance: ModelProvenance
    limitations: List[str] = Field(default_factory=list)
    latency_ms: float = Field(..., ge=0.0)
