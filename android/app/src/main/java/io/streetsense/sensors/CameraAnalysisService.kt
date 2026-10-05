package io.streetsense.sensors

import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import io.streetsense.domain.model.FrameMetadata
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.nio.ByteBuffer
import kotlin.math.abs

class CameraAnalysisService : ImageAnalysis.Analyzer {
    private val _frameFlow = MutableSharedFlow<FrameMetadata>(extraBufferCapacity = 8)
    val frameFlow: SharedFlow<FrameMetadata> = _frameFlow.asSharedFlow()

    private var lastAnalyzedTimestamp = 0L
    private val minIntervalMs = 200L // 5 FPS edge sampling to prevent thermal/battery throttling

    override fun analyze(image: ImageProxy) {
        val currentMs = System.currentTimeMillis()
        if (currentMs - lastAnalyzedTimestamp < minIntervalMs) {
            image.close()
            return
        }
        lastAnalyzedTimestamp = currentMs

        val timestampNs = image.imageInfo.timestamp
        val width = image.width
        val height = image.height
        val rotation = image.imageInfo.rotationDegrees

        // Calculate real luminance and sharpness from Y (luminance) plane buffer (YUV_420_888)
        val plane = image.planes[0]
        val buffer: ByteBuffer = plane.buffer
        val data = ByteArray(buffer.remaining())
        buffer.get(data)

        var sumLuminance = 0L
        var sumGradientVariance = 0.0
        val sampleStep = 8
        var sampledCount = 0

        for (i in 0 until data.size - sampleStep step sampleStep) {
            val p1 = (data[i].toInt() and 0xFF)
            val p2 = (data[i + sampleStep].toInt() and 0xFF)
            sumLuminance += p1

            // Gradient difference for sharpness/blur estimation
            val diff = abs(p1 - p2)
            sumGradientVariance += (diff * diff)
            sampledCount++
        }

        val meanLuminance = if (sampledCount > 0) (sumLuminance.toFloat() / sampledCount) else 128.0f
        val sharpnessScore = if (sampledCount > 0) (sumGradientVariance.toFloat() / sampledCount) else 0.0f

        val metadata = FrameMetadata(
            timestamp_ns = timestampNs,
            wall_clock_timestamp_ms = System.currentTimeMillis(),
            width = width,
            height = height,
            format = "YUV_420_888",
            luminance_mean = meanLuminance,
            blur_score = sharpnessScore,
            rotation_degrees = rotation,
            is_valid = true
        )

        _frameFlow.tryEmit(metadata)
        image.close()
    }

    fun shutdown() {
        // Safe analyzer cleanup
    }
}
