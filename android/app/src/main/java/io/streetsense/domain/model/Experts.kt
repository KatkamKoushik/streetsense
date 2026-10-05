package io.streetsense.domain.model

enum class ExpertCapability {
    SENSOR_QUALITY,
    MOTION_ANALYSIS,
    LOCATION_ANALYSIS,
    OBJECT_DETECTION,
    SCENE_ANALYSIS,
    ROAD_ANALYSIS,
    TEMPORAL_CHANGE,
    ILLUMINATION_ANALYSIS,
    HAZARD_ANALYSIS,
    SPATIAL_CONTEXT,
    EVIDENCE_FUSION,
    ARBITRATION,
    REASONING
}

enum class ExecutionStatus {
    AVAILABLE,
    SELECTED,
    RUNNING,
    SUCCESS,
    DEGRADED,
    UNAVAILABLE,
    NOT_IMPLEMENTED,
    TIMEOUT,
    FAILED,
    SKIPPED
}

data class ModelProvenance(
    val runtime: String,
    val model_name: String,
    val version: String,
    val quantization: String? = null,
    val device: String = "cpu",
    val sha256: String? = null
)

data class ExpertResult(
    val expert_id: String,
    val capability: ExpertCapability,
    val status: ExecutionStatus,
    val prediction: String? = null,
    val confidence: Float,
    val evidence: List<Map<String, Any>> = emptyList(),
    val timestamp_ns: Long,
    val provenance: ModelProvenance,
    val limitations: List<String> = emptyList(),
    val latency_ms: Float
)
