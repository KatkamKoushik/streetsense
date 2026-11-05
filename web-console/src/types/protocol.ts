export enum SensorType {
  ACCELEROMETER = "ACCELEROMETER",
  GYROSCOPE = "GYROSCOPE",
  MAGNETOMETER = "MAGNETOMETER",
  AMBIENT_LIGHT = "AMBIENT_LIGHT",
  GPS = "GPS",
  CAMERA_FRAME = "CAMERA_FRAME",
  STEP_DETECTOR = "STEP_DETECTOR",
  PROXIMITY = "PROXIMITY",
  BAROMETER = "BAROMETER",
}

export enum SensorAccuracy {
  UNRELIABLE = "UNRELIABLE",
  LOW = "LOW",
  MEDIUM = "MEDIUM",
  HIGH = "HIGH",
}

export enum Orientation {
  PORTRAIT = "PORTRAIT",
  LANDSCAPE_LEFT = "LANDSCAPE_LEFT",
  LANDSCAPE_RIGHT = "LANDSCAPE_RIGHT",
  PORTRAIT_INVERTED = "PORTRAIT_INVERTED",
  UNKNOWN = "UNKNOWN",
}

export interface SensorSnapshot {
  sensor_type: SensorType;
  timestamp_ns: number;
  values: number[];
  accuracy: SensorAccuracy;
  orientation: Orientation;
  metadata?: Record<string, any>;
}

export interface LocationSnapshot {
  latitude: number;
  longitude: number;
  altitude?: number;
  accuracy_meters: number;
  speed_mps?: number;
  bearing_degrees?: number;
  timestamp_ns: number;
}

export enum ExpertCapability {
  SENSOR_QUALITY = "SENSOR_QUALITY",
  MOTION_ANALYSIS = "MOTION_ANALYSIS",
  LOCATION_ANALYSIS = "LOCATION_ANALYSIS",
  OBJECT_DETECTION = "OBJECT_DETECTION",
  SCENE_ANALYSIS = "SCENE_ANALYSIS",
  ROAD_ANALYSIS = "ROAD_ANALYSIS",
  TEMPORAL_CHANGE = "TEMPORAL_CHANGE",
  ILLUMINATION_ANALYSIS = "ILLUMINATION_ANALYSIS",
  HAZARD_ANALYSIS = "HAZARD_ANALYSIS",
  SPATIAL_CONTEXT = "SPATIAL_CONTEXT",
  EVIDENCE_FUSION = "EVIDENCE_FUSION",
  ARBITRATION = "ARBITRATION",
  REASONING = "REASONING",
}

export enum ExecutionStatus {
  AVAILABLE = "AVAILABLE",
  SELECTED = "SELECTED",
  RUNNING = "RUNNING",
  SUCCESS = "SUCCESS",
  DEGRADED = "DEGRADED",
  UNAVAILABLE = "UNAVAILABLE",
  NOT_IMPLEMENTED = "NOT_IMPLEMENTED",
  TIMEOUT = "TIMEOUT",
  FAILED = "FAILED",
  SKIPPED = "SKIPPED",
}

export interface ModelProvenance {
  runtime: string;
  model_name: string;
  version: string;
  quantization?: string;
  device: string;
  sha256?: string;
}

export interface ExpertResult {
  expert_id: string;
  capability: ExpertCapability;
  status: ExecutionStatus;
  prediction?: string;
  confidence: number;
  evidence: Record<string, any>[];
  timestamp_ns: number;
  provenance: ModelProvenance;
  limitations: string[];
  latency_ms: number;
}

export enum EvidenceType {
  SENSOR_QUALITY_CHECK = "SENSOR_QUALITY_CHECK",
  KINETIC_JERK = "KINETIC_JERK",
  SUDDEN_DECELERATION = "SUDDEN_DECELERATION",
  PEDESTRIAN_FALL = "PEDESTRIAN_FALL",
  HIGH_SPEED_TRANSIT = "HIGH_SPEED_TRANSIT",
  ROAD_BOUNDARY_CROSSING = "ROAD_BOUNDARY_CROSSING",
  LOW_LIGHT_ENVIRONMENT = "LOW_LIGHT_ENVIRONMENT",
  GLARE_EXPOSURE = "GLARE_EXPOSURE",
  VISUAL_OBSTRUCTION = "VISUAL_OBSTRUCTION",
  APPROACHING_VEHICLE = "APPROACHING_VEHICLE",
  TEMPORAL_PERSISTENCE = "TEMPORAL_PERSISTENCE",
  SPATIAL_PROXIMITY = "SPATIAL_PROXIMITY",
}

export interface EvidenceItem {
  evidence_id: string;
  expert_id: string;
  evidence_type: EvidenceType;
  confidence: number;
  timestamp_ns: number;
  source_sensor: string;
  attributes: Record<string, any>;
  weight: number;
}

export enum EventSeverity {
  INFO = "INFO",
  NOTICE = "NOTICE",
  WARNING = "WARNING",
  HIGH_RISK = "HIGH_RISK",
  CRITICAL = "CRITICAL",
}

export enum EventCategory {
  PEDESTRIAN_FALL_OR_IMPACT = "PEDESTRIAN_FALL_OR_IMPACT",
  VEHICLE_APPROACH_COLLISION = "VEHICLE_APPROACH_COLLISION",
  ROAD_HAZARD_OBSTRUCTION = "ROAD_HAZARD_OBSTRUCTION",
  POOR_VISIBILITY_HAZARD = "POOR_VISIBILITY_HAZARD",
  ANOMALOUS_MOTION = "ANOMALOUS_MOTION",
  SENSOR_MALFUNCTION = "SENSOR_MALFUNCTION",
}

export interface ConfidenceBreakdown {
  prediction_confidence: number;
  input_quality: number;
  temporal_consistency: number;
  sensor_reliability: number;
  cross_expert_agreement: number;
  geometric_consistency: number;
  evidence_quality: number;
  final_decision_confidence: number;
}

export interface DetectedEvent {
  event_id: string;
  session_id: string;
  timestamp_ns: number;
  category: EventCategory;
  severity: EventSeverity;
  confidence_breakdown: ConfidenceBreakdown;
  contributing_evidence_ids: string[];
  contributing_evidence?: EvidenceItem[];
  explanation: string;
  haptic_pattern: string;
  latitude?: number;
  longitude?: number;
  is_dismissed: boolean;
  metadata?: Record<string, any>;
}

export enum EventType {
  SESSION_STARTED = "session.started",
  SESSION_UPDATED = "session.updated",
  SENSOR_STATUS = "sensor.status",
  INFERENCE_STARTED = "inference.started",
  INFERENCE_COMPLETED = "inference.completed",
  EXPERT_STARTED = "expert.started",
  EXPERT_COMPLETED = "expert.completed",
  EXPERT_FAILED = "expert.failed",
  EVIDENCE_CREATED = "evidence.created",
  EVENT_DETECTED = "event.detected",
  EVENT_UPDATED = "event.updated",
  ALERT_TRIGGERED = "alert.triggered",
  ALERT_DISMISSED = "alert.dismissed",
  DEVICE_STATUS = "device.status",
  CONNECTION_STATUS = "connection.status",
  HEARTBEAT_PING = "heartbeat.ping",
  HEARTBEAT_PONG = "heartbeat.pong",
}

export interface DeviceStatusPayload {
  battery_level: number;
  battery_temperature_c: number;
  is_charging: boolean;
  thermal_state: string;
  network_type: string;
  active_sensors: string[];
  degraded_sensors: string[];
}

export interface WsMessageEnvelope<T = any> {
  message_id: string;
  correlation_id: string;
  session_id: string;
  device_id: string;
  timestamp_ns: number;
  event_type: EventType;
  sequence_number: number;
  payload: T;
}
