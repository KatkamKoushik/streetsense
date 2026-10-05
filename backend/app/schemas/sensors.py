from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SensorType(str, Enum):
    ACCELEROMETER = "ACCELEROMETER"
    GYROSCOPE = "GYROSCOPE"
    MAGNETOMETER = "MAGNETOMETER"
    AMBIENT_LIGHT = "AMBIENT_LIGHT"
    GPS = "GPS"
    CAMERA_FRAME = "CAMERA_FRAME"
    STEP_DETECTOR = "STEP_DETECTOR"
    PROXIMITY = "PROXIMITY"
    BAROMETER = "BAROMETER"


class SensorAccuracy(str, Enum):
    UNRELIABLE = "UNRELIABLE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SENSOR_UNAVAILABLE = "SENSOR_UNAVAILABLE"


class Orientation(str, Enum):
    PORTRAIT = "PORTRAIT"
    LANDSCAPE_LEFT = "LANDSCAPE_LEFT"
    LANDSCAPE_RIGHT = "LANDSCAPE_RIGHT"
    PORTRAIT_INVERTED = "PORTRAIT_INVERTED"
    UNKNOWN = "UNKNOWN"


class Vector3D(BaseModel):
    x: float
    y: float
    z: float


class SensorSnapshot(BaseModel):
    sensor_type: SensorType
    timestamp_ns: int = Field(..., description="Nanosecond timestamp from hardware clock")
    wall_clock_timestamp_ms: Optional[int] = Field(default=None, description="System epoch millisecond timestamp")
    values: List[float] = Field(..., description="Raw or calibrated float values")
    accuracy: SensorAccuracy = SensorAccuracy.HIGH
    orientation: Orientation = Orientation.UNKNOWN
    is_available: bool = True
    max_range: Optional[float] = None
    is_valid: bool = True
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FrameMetadata(BaseModel):
    timestamp_ns: int
    wall_clock_timestamp_ms: Optional[int] = None
    width: int
    height: int
    format: str = "YUV_420_888"
    luminance_mean: float = Field(default=0.0, ge=0.0, le=255.0)
    blur_score: float = Field(default=0.0, ge=0.0, description="Laplacian variance sharpness score")
    rotation_degrees: int = 0
    is_valid: bool = True
    degradation_reason: Optional[str] = None


class LocationSnapshot(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    altitude: Optional[float] = None
    accuracy_meters: Optional[float] = Field(default=None, ge=0.0)
    speed_mps: Optional[float] = Field(None, ge=0.0)
    bearing_degrees: Optional[float] = Field(None, ge=0.0, le=360.0)
    timestamp_ns: int
    wall_clock_timestamp_ms: Optional[int] = None
    is_available: bool = True
