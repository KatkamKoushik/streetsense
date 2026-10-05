package io.streetsense.domain.model

enum class EventType(val wireName: String) {
    SESSION_STARTED("session.started"),
    SESSION_UPDATED("session.updated"),
    SENSOR_STATUS("sensor.status"),
    INFERENCE_STARTED("inference.started"),
    INFERENCE_COMPLETED("inference.completed"),
    EXPERT_STARTED("expert.started"),
    EXPERT_COMPLETED("expert.completed"),
    EXPERT_FAILED("expert.failed"),
    EVIDENCE_CREATED("evidence.created"),
    EVENT_DETECTED("event.detected"),
    EVENT_UPDATED("event.updated"),
    ALERT_TRIGGERED("alert.triggered"),
    ALERT_DISMISSED("alert.dismissed"),
    DEVICE_STATUS("device.status"),
    CONNECTION_STATUS("connection.status"),
    HEARTBEAT_PING("heartbeat.ping"),
    HEARTBEAT_PONG("heartbeat.pong")
}

data class DeviceStatusPayload(
    val battery_level: Float,
    val battery_temperature_c: Float,
    val is_charging: Boolean,
    val thermal_state: String = "NORMAL",
    val network_type: String = "WIFI",
    val active_sensors: List<String> = emptyList(),
    val degraded_sensors: List<String> = emptyList()
)

data class WsMessageEnvelope<T>(
    val message_id: String,
    val correlation_id: String,
    val session_id: String,
    val device_id: String,
    val timestamp_ns: Long,
    val event_type: String,
    val sequence_number: Long,
    val payload: T
)
