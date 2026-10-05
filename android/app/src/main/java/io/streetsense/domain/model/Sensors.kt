package io.streetsense.domain.model

enum class SensorType {
    ACCELEROMETER,
    GYROSCOPE,
    MAGNETOMETER,
    AMBIENT_LIGHT,
    GPS,
    CAMERA_FRAME,
    STEP_DETECTOR,
    PROXIMITY,
    BAROMETER
}

enum class SensorAccuracy {
    UNRELIABLE,
    LOW,
    MEDIUM,
    HIGH,
    SENSOR_UNAVAILABLE
}

enum class Orientation {
    PORTRAIT,
    LANDSCAPE_LEFT,
    LANDSCAPE_RIGHT,
    PORTRAIT_INVERTED,
    UNKNOWN
}

data class SensorSnapshot(
    val sensor_type: SensorType,
    val timestamp_ns: Long,
    val wall_clock_timestamp_ms: Long = System.currentTimeMillis(),
    val values: List<Float>,
    val accuracy: SensorAccuracy = SensorAccuracy.HIGH,
    val orientation: Orientation = Orientation.UNKNOWN,
    val is_available: Boolean = true,
    val max_range: Float? = null,
    val is_valid: Boolean = true,
    val device_id: String? = null,
    val session_id: String? = null,
    val metadata: Map<String, Any> = emptyMap()
)

data class LocationSnapshot(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double? = null,
    val accuracy_meters: Float? = null,
    val speed_mps: Float? = null,
    val bearing_degrees: Float? = null,
    val timestamp_ns: Long,
    val wall_clock_timestamp_ms: Long = System.currentTimeMillis(),
    val is_available: Boolean = true
)

data class FrameMetadata(
    val timestamp_ns: Long,
    val wall_clock_timestamp_ms: Long = System.currentTimeMillis(),
    val width: Int,
    val height: Int,
    val format: String = "YUV_420_888",
    val luminance_mean: Float = 0.0f,
    val blur_score: Float = 0.0f,
    val rotation_degrees: Int = 0,
    val is_valid: Boolean = true,
    val degradation_reason: String? = null
)
