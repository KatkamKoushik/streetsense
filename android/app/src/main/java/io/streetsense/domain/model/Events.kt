package io.streetsense.domain.model

enum class EventSeverity {
    INFO,
    NOTICE,
    WARNING,
    HIGH_RISK,
    CRITICAL
}

enum class EventCategory {
    PEDESTRIAN_FALL_OR_IMPACT,
    VEHICLE_APPROACH_COLLISION,
    ROAD_HAZARD_OBSTRUCTION,
    POOR_VISIBILITY_HAZARD,
    ANOMALOUS_MOTION,
    SENSOR_MALFUNCTION
}

data class ConfidenceBreakdown(
    val prediction_confidence: Float,
    val input_quality: Float,
    val temporal_consistency: Float,
    val sensor_reliability: Float,
    val cross_expert_agreement: Float,
    val geometric_consistency: Float,
    val evidence_quality: Float,
    val final_decision_confidence: Float
)

data class DetectedEvent(
    val event_id: String,
    val session_id: String,
    val timestamp_ns: Long,
    val category: EventCategory,
    val severity: EventSeverity,
    val confidence_breakdown: ConfidenceBreakdown,
    val contributing_evidence_ids: List<String> = emptyList(),
    val contributing_evidence: List<EvidenceItem> = emptyList(),
    val explanation: String,
    val haptic_pattern: String = "PULSE_ALERT",
    val latitude: Double? = null,
    val longitude: Double? = null,
    val is_dismissed: Boolean = false,
    val metadata: Map<String, Any> = emptyMap()
)
