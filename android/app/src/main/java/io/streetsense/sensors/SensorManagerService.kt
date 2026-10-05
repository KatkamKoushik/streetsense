package io.streetsense.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import io.streetsense.domain.model.SensorAccuracy
import io.streetsense.domain.model.SensorSnapshot
import io.streetsense.domain.model.SensorType
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow

class SensorManagerService(context: Context) : SensorEventListener {
    private val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager

    private val accelerometer: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val gyroscope: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val magnetometer: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
    private val lightSensor: Sensor? = sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT)

    private val _sensorFlow = MutableSharedFlow<SensorSnapshot>(extraBufferCapacity = 256)
    val sensorFlow: SharedFlow<SensorSnapshot> = _sensorFlow.asSharedFlow()

    @Volatile
    private var isListening = false

    var deviceId: String? = null
    var sessionId: String? = null

    fun getSensorAvailability(): Map<SensorType, Boolean> {
        return mapOf(
            SensorType.ACCELEROMETER to (accelerometer != null),
            SensorType.GYROSCOPE to (gyroscope != null),
            SensorType.MAGNETOMETER to (magnetometer != null),
            SensorType.AMBIENT_LIGHT to (lightSensor != null)
        )
    }

    fun startListening() {
        if (isListening) return
        isListening = true

        // Register available hardware sensors
        accelerometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        } ?: emitUnavailable(SensorType.ACCELEROMETER)

        gyroscope?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        } ?: emitUnavailable(SensorType.GYROSCOPE)

        magnetometer?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        } ?: emitUnavailable(SensorType.MAGNETOMETER)

        lightSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_NORMAL)
        } ?: emitUnavailable(SensorType.AMBIENT_LIGHT)
    }

    private fun emitUnavailable(sensorType: SensorType) {
        val nowNs = System.nanoTime()
        val snapshot = SensorSnapshot(
            sensor_type = sensorType,
            timestamp_ns = nowNs,
            wall_clock_timestamp_ms = System.currentTimeMillis(),
            values = emptyList(),
            accuracy = SensorAccuracy.SENSOR_UNAVAILABLE,
            is_available = false,
            device_id = deviceId,
            session_id = sessionId
        )
        _sensorFlow.tryEmit(snapshot)
    }

    fun stopListening() {
        if (!isListening) return
        isListening = false
        // Safely release all registered listeners to prevent battery drain or memory leaks
        sensorManager.unregisterListener(this)
    }

    override fun onSensorChanged(event: SensorEvent?) {
        if (!isListening || event == null) return

        val sensorType = when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> SensorType.ACCELEROMETER
            Sensor.TYPE_GYROSCOPE -> SensorType.GYROSCOPE
            Sensor.TYPE_MAGNETIC_FIELD -> SensorType.MAGNETOMETER
            Sensor.TYPE_LIGHT -> SensorType.AMBIENT_LIGHT
            else -> return
        }

        val maxRange = event.sensor.maximumRange
        val rawValues = event.values.toList()
        var isValid = true
        val metadata = mutableMapOf<String, Any>()

        // 1. Check for NaN or Infinite values
        if (rawValues.any { it.isNaN() || it.isInfinite() }) {
            isValid = false
            metadata["glitch_reason"] = "Non-finite sensor values (NaN/Inf)"
        }

        // 2. Check for impossible/negative timestamp
        if (event.timestamp <= 0L) {
            isValid = false
            metadata["glitch_reason"] = "Invalid sensor hardware timestamp <= 0"
        }

        // 3. Sensor range check: value significantly exceeds hardware maximum range
        // Provide 20% margin for peak saturation vs driver glitch
        if (maxRange > 0f && rawValues.any { kotlin.math.abs(it) > maxRange * 1.5f }) {
            isValid = false
            metadata["glitch_reason"] = "Hardware maximumRange ($maxRange) exceeded"
        }

        val accuracy = if (!isValid) {
            SensorAccuracy.UNRELIABLE
        } else when (event.accuracy) {
            SensorManager.SENSOR_STATUS_UNRELIABLE -> SensorAccuracy.UNRELIABLE
            SensorManager.SENSOR_STATUS_ACCURACY_LOW -> SensorAccuracy.LOW
            SensorManager.SENSOR_STATUS_ACCURACY_MEDIUM -> SensorAccuracy.MEDIUM
            SensorManager.SENSOR_STATUS_ACCURACY_HIGH -> SensorAccuracy.HIGH
            else -> SensorAccuracy.HIGH
        }

        val snapshot = SensorSnapshot(
            sensor_type = sensorType,
            timestamp_ns = event.timestamp,
            wall_clock_timestamp_ms = System.currentTimeMillis(),
            values = rawValues,
            accuracy = accuracy,
            is_available = true,
            max_range = maxRange,
            is_valid = isValid,
            device_id = deviceId,
            session_id = sessionId,
            metadata = metadata
        )

        _sensorFlow.tryEmit(snapshot)
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
        // Automatically handled on next onSensorChanged event
    }
}
