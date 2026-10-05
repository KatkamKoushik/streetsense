package io.streetsense.domain.model

enum class EvidenceType {
    SENSOR_QUALITY_CHECK,
    KINETIC_JERK,
    SUDDEN_DECELERATION,
    PEDESTRIAN_FALL,
    HIGH_SPEED_TRANSIT,
    ROAD_BOUNDARY_CROSSING,
    LOW_LIGHT_ENVIRONMENT,
    GLARE_EXPOSURE,
    VISUAL_OBSTRUCTION,
    APPROACHING_VEHICLE,
    TEMPORAL_PERSISTENCE,
    SPATIAL_PROXIMITY
}

data class EvidenceItem(
    val evidence_id: String,
    val expert_id: String,
    val evidence_type: EvidenceType,
    val confidence: Float,
    val timestamp_ns: Long,
    val source_sensor: String,
    val attributes: Map<String, Any> = emptyMap(),
    val weight: Float = 1.0f
)
