package io.streetsense.ui

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import io.streetsense.data.AppDatabase
import io.streetsense.data.LocalEventEntity
import io.streetsense.data.StreetSenseWebSocketClient
import io.streetsense.domain.model.*
import io.streetsense.engine.NativeEvidenceFusionEngine
import io.streetsense.engine.NativeSelectiveRouter
import io.streetsense.engine.RoutingInstrumentation
import io.streetsense.engine.TemporalRingBuffer
import io.streetsense.sensors.CameraAnalysisService
import io.streetsense.sensors.LocationService
import io.streetsense.sensors.SensorManagerService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.math.sqrt

class MainActivity : ComponentActivity() {
    private lateinit var sensorService: SensorManagerService
    private lateinit var locationService: LocationService
    private val cameraAnalysisService = CameraAnalysisService()
    private val cameraExecutor = Executors.newSingleThreadExecutor()

    private val ringBuffer = TemporalRingBuffer(120)
    private val router = NativeSelectiveRouter()
    private val fusionEngine = NativeEvidenceFusionEngine()
    private lateinit var db: AppDatabase
    private lateinit var wsClient: StreetSenseWebSocketClient

    private var hasCameraPermission by mutableStateOf(false)
    private var hasLocationPermission by mutableStateOf(false)
    private var isGatewayConnected by mutableStateOf(false)

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        hasCameraPermission = permissions[Manifest.permission.CAMERA] == true
        hasLocationPermission = permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true
        if (hasLocationPermission) {
            locationService.startTracking(true)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        sensorService = SensorManagerService(this)
        locationService = LocationService(this)
        db = AppDatabase.getDatabase(this)

        val deviceId = "android_" + Build.MODEL.replace(" ", "_").lowercase()
        sensorService.deviceId = deviceId

        // Configurable gateway URL (defaults to 127.0.0.1:8000 via adb reverse, or user-configurable)
        wsClient = StreetSenseWebSocketClient(
            serverUrl = "ws://127.0.0.1:8000/ws/telemetry",
            deviceId = deviceId,
            db = db,
            onConnectionChanged = { connected ->
                isGatewayConnected = connected
                if (connected) {
                    sendDeviceStatus()
                }
            }
        )

        checkPermissions()

        setContent {
            StreetSenseMobileApp(
                sensorService = sensorService,
                locationService = locationService,
                cameraAnalysisService = cameraAnalysisService,
                hasCameraPermission = hasCameraPermission,
                hasLocationPermission = hasLocationPermission,
                isGatewayConnected = isGatewayConnected,
                currentServerUrl = wsClient.getServerUrl(),
                onUpdateServerUrl = { newUrl -> wsClient.updateServerUrl(newUrl) },
                onTriggerHaptic = { pattern -> triggerHaptic(pattern) },
                onEventGenerated = { event ->
                    persistAndTransmitEvent(event)
                },
                onTransmitTelemetryBatch = { snapshots, location, frameMetadata ->
                    transmitTelemetry(snapshots, location, frameMetadata)
                },
                onTransmitExpertRuns = { runs ->
                    transmitExpertRuns(runs)
                }
            )
        }
    }

    private fun checkPermissions() {
        val cameraGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        val locationGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

        hasCameraPermission = cameraGranted
        hasLocationPermission = locationGranted

        if (!cameraGranted || !locationGranted) {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.CAMERA,
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        } else {
            locationService.startTracking(true)
        }
    }

    private fun triggerHaptic(pattern: String) {
        val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val manager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            manager.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val timings = when (pattern) {
                "STRONG_DOUBLE_PULSE" -> longArrayOf(0, 200, 100, 300)
                "RAPID_PULSE" -> longArrayOf(0, 100, 50, 100)
                else -> longArrayOf(0, 150)
            }
            vibrator.vibrate(VibrationEffect.createWaveform(timings, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(250)
        }
    }

    private fun persistAndTransmitEvent(event: DetectedEvent) {
        lifecycleScope.launch(Dispatchers.IO) {
            val entity = LocalEventEntity(
                event_id = event.event_id,
                session_id = event.session_id,
                category = event.category.name,
                severity = event.severity.name,
                timestamp_ns = event.timestamp_ns,
                explanation = event.explanation,
                haptic_pattern = event.haptic_pattern,
                latitude = event.latitude,
                longitude = event.longitude,
                is_synced = wsClient.isConnected
            )
            db.eventDao().insertEvent(entity)

            // Realtime WebSocket broadcast
            wsClient.sendEnvelope(
                eventType = EventType.EVENT_DETECTED,
                sessionId = event.session_id,
                payload = mapOf("event" to event)
            )
        }
    }

    private fun transmitTelemetry(
        snapshots: List<SensorSnapshot>,
        location: LocationSnapshot?,
        frameMetadata: FrameMetadata?
    ) {
        if (snapshots.isEmpty()) return
        val sessionId = sensorService.sessionId ?: "sess_active"
        wsClient.sendEnvelope(
            eventType = EventType.SENSOR_STATUS,
            sessionId = sessionId,
            payload = mapOf(
                "snapshots" to snapshots.takeLast(10),
                "location" to location,
                "frame_metadata" to frameMetadata
            )
        )
    }

    private fun transmitExpertRuns(runs: List<ExpertResult>) {
        if (runs.isEmpty()) return
        val sessionId = sensorService.sessionId ?: "sess_active"
        for (res in runs) {
            wsClient.sendEnvelope(
                eventType = EventType.EXPERT_COMPLETED,
                sessionId = sessionId,
                payload = mapOf(
                    "expert_result" to res,
                    "evidence" to res.evidence
                )
            )
        }
    }

    private fun sendDeviceStatus() {
        val batteryManager = getSystemService(Context.BATTERY_SERVICE) as? android.os.BatteryManager
        val batteryLevel = batteryManager?.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY)?.toFloat() ?: 85f
        val isCharging = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val status = batteryManager?.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_STATUS)
            status == android.os.BatteryManager.BATTERY_STATUS_CHARGING || status == android.os.BatteryManager.BATTERY_STATUS_FULL
        } else false

        val activeSensors = listOf("ACCELEROMETER", "GYROSCOPE", "MAGNETOMETER", "AMBIENT_LIGHT", "GPS")
        val payload = mapOf(
            "device_status" to mapOf(
                "battery_level" to batteryLevel,
                "battery_temperature_c" to 31.5f,
                "is_charging" to isCharging,
                "thermal_state" to "NORMAL",
                "network_type" to "WIFI",
                "active_sensors" to activeSensors,
                "degraded_sensors" to emptyList<String>()
            )
        )
        val sessionId = sensorService.sessionId ?: "sess_active"
        wsClient.sendEnvelope(
            eventType = EventType.DEVICE_STATUS,
            sessionId = sessionId,
            payload = payload
        )
    }

    override fun onResume() {
        super.onResume()
        sensorService.startListening()
        locationService.startTracking(hasLocationPermission)
        wsClient.connect()
    }

    override fun onPause() {
        super.onPause()
        sensorService.stopListening()
        locationService.stopTracking()
        wsClient.disconnect()
    }

    override fun onDestroy() {
        super.onDestroy()
        cameraExecutor.shutdown()
        cameraAnalysisService.shutdown()
    }
}

@Composable
fun StreetSenseMobileApp(
    sensorService: SensorManagerService,
    locationService: LocationService,
    cameraAnalysisService: CameraAnalysisService,
    hasCameraPermission: Boolean,
    hasLocationPermission: Boolean,
    isGatewayConnected: Boolean,
    currentServerUrl: String,
    onUpdateServerUrl: (String) -> Unit,
    onTriggerHaptic: (String) -> Unit,
    onEventGenerated: (DetectedEvent) -> Unit,
    onTransmitTelemetryBatch: (List<SensorSnapshot>, LocationSnapshot?, FrameMetadata?) -> Unit,
    onTransmitExpertRuns: (List<ExpertResult>) -> Unit = {}
) {
    val router = remember { NativeSelectiveRouter() }
    val fusionEngine = remember { NativeEvidenceFusionEngine() }
    val ringBuffer = remember { TemporalRingBuffer(120) }

    var latestSnapshot by remember { mutableStateOf<SensorSnapshot?>(null) }
    var latestAccelSnapshot by remember { mutableStateOf<SensorSnapshot?>(null) }
    var latestLocation by remember { mutableStateOf<LocationSnapshot?>(null) }
    var latestFrame by remember { mutableStateOf<FrameMetadata?>(null) }
    var activeAlert by remember { mutableStateOf<DetectedEvent?>(null) }

    val expertRuns = remember { mutableStateListOf<ExpertResult>() }
    var routingInfo by remember { mutableStateOf<RoutingInstrumentation?>(null) }

    val sessionId = remember { "sess_${UUID.randomUUID().toString().take(8)}" }
    var showUrlDialog by remember { mutableStateOf(false) }
    var urlInput by remember { mutableStateOf(currentServerUrl) }

    LaunchedEffect(Unit) {
        sensorService.sessionId = sessionId
    }

    // Collect hardware sensor flow
    LaunchedEffect(Unit) {
        var sampleCounter = 0
        sensorService.sensorFlow.collect { snap ->
            latestSnapshot = snap
            ringBuffer.push(snap)
            sampleCounter++

            // Selective Multi-Expert evaluation on IMU updates
            if (snap.sensor_type == SensorType.ACCELEROMETER) {
                latestAccelSnapshot = snap
                val recent = ringBuffer.getRecent(30)
                val (results, instrumentation) = router.routeAndEvaluate(recent, latestLocation, latestFrame)
                expertRuns.clear()
                expertRuns.addAll(results)
                routingInfo = instrumentation

                val event = fusionEngine.fuse(sessionId, results, latestLocation)
                if (event != null) {
                    activeAlert = event
                    onTriggerHaptic(event.haptic_pattern)
                    onEventGenerated(event)
                } else if (instrumentation.escalationLevel == 0) {
                    // State Machine Consistency:
                    // When baseline motion returns to normal and router is in Level 0,
                    // clear the active warning alert.
                    activeAlert = null
                }

                // Batch transmit telemetry every ~10 samples to conserve bandwidth
                if (sampleCounter % 10 == 0) {
                    onTransmitTelemetryBatch(recent, latestLocation, latestFrame)
                    onTransmitExpertRuns(results)
                }
            }
        }
    }

    // Collect GPS location flow
    LaunchedEffect(Unit) {
        locationService.locationFlow.collect { loc ->
            latestLocation = loc
        }
    }

    // Collect CameraX frame metadata
    LaunchedEffect(Unit) {
        cameraAnalysisService.frameFlow.collect { frame ->
            latestFrame = frame
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = Color(0xFF030712)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            // Header Bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "StreetSense",
                        fontSize = 22.sp,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                    Text(
                        text = "Edge Multi-Expert Sentinel",
                        fontSize = 11.sp,
                        color = Color(0xFF94A3B8)
                    )
                }

                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Button(
                        onClick = { showUrlDialog = true },
                        colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1E293B)),
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text(
                            text = if (isGatewayConnected) "LIVE LINK" else "OFFLINE",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (isGatewayConnected) Color(0xFF10B981) else Color(0xFFF43F5E)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // CameraX Live Optical Viewfinder
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(130.dp)
                    .background(Color(0xFF0B132B), RoundedCornerShape(12.dp))
                    .border(1.dp, Color(0xFF38BDF8).copy(alpha = 0.25f), RoundedCornerShape(12.dp))
            ) {
                if (hasCameraPermission) {
                    CameraPreviewComposable(cameraAnalysisService)
                } else {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text(text = "Camera Permission Required", color = Color(0xFF94A3B8), fontSize = 12.sp)
                    }
                }

                // Optical Metadata Overlay HUD
                latestFrame?.let { frame ->
                    Box(
                        modifier = Modifier
                            .align(Alignment.BottomStart)
                            .padding(8.dp)
                            .background(Color.Black.copy(alpha = 0.6f), RoundedCornerShape(6.dp))
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = "${frame.width}x${frame.height} | Lux: ${frame.luminance_mean.toInt()} | Sharpness: ${frame.blur_score.toInt()}",
                            color = Color(0xFF38BDF8),
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            // Active Alert Card
            activeAlert?.let { alert ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (alert.severity == EventSeverity.HIGH_RISK) Color(0xFFF43F5E).copy(alpha = 0.2f) else Color(0xFFF59E0B).copy(alpha = 0.2f)
                    ),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Column(modifier = Modifier.padding(12.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(text = alert.category.name, fontWeight = FontWeight.Bold, color = Color.White, fontSize = 14.sp)
                            Text(text = alert.severity.name, fontWeight = FontWeight.ExtraBold, color = if (alert.severity == EventSeverity.HIGH_RISK) Color(0xFFF43F5E) else Color(0xFFF59E0B), fontSize = 11.sp)
                        }
                        Text(text = alert.explanation, color = Color(0xFFE2E8F0), fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // Real-Time Sensor Telemetry HUD
            Text(text = "HARDWARE SENSOR STREAM", fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF64748B))
            Spacer(modifier = Modifier.height(6.dp))

            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                // Accelerometer (Guaranteed dedicated ACCELEROMETER sensor channel - never overwritten by Magnetometer or Gyro)
                Card(modifier = Modifier.weight(1f), colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A).copy(alpha = 0.7f)), shape = RoundedCornerShape(8.dp)) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(text = "ACCEL 3-AXIS", fontSize = 9.sp, color = Color(0xFF94A3B8))
                        val vals = latestAccelSnapshot?.values ?: emptyList()
                        val mag = if (vals.size >= 3) sqrt(vals[0]*vals[0] + vals[1]*vals[1] + vals[2]*vals[2]) else 9.80f
                        val isGlitch = mag > 200f || (latestAccelSnapshot?.max_range != null && mag > (latestAccelSnapshot?.max_range ?: 200f) * 1.05f)
                        val textStr = if (isGlitch) String.format("%.1f m/s² (SPIKE)", mag) else String.format("%.2f m/s²", mag)
                        Text(text = textStr, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = if (isGlitch) Color(0xFFF43F5E) else Color.White)
                    }
                }

                // Location / GPS (Strict sentinel handling: ±999m treated as NO FIX / SEARCHING, never valid accuracy)
                Card(modifier = Modifier.weight(1f), colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A).copy(alpha = 0.7f)), shape = RoundedCornerShape(8.dp)) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(text = "GPS ACCURACY", fontSize = 9.sp, color = Color(0xFF94A3B8))
                        val isAvail = latestLocation?.is_available == true
                        val acc = latestLocation?.accuracy_meters
                        val displayText = when {
                            !isAvail || acc == null || acc >= 900.0f -> "NO FIX"
                            acc in 0.1f..15.0f -> String.format("±%.1fm", acc)
                            else -> String.format("±%.1fm", acc)
                        }
                        val displayColor = when {
                            !isAvail || acc == null || acc >= 900.0f -> Color(0xFF94A3B8)
                            acc in 0.1f..15.0f -> Color(0xFF10B981)
                            else -> Color(0xFFF59E0B)
                        }
                        Text(text = displayText, fontSize = 15.sp, fontWeight = FontWeight.Bold, color = displayColor)
                    }
                }
            }

            Spacer(modifier = Modifier.height(10.dp))

            // Routing Instrumentation & Battery Optimization Note
            routingInfo?.let { info ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFF0B132B).copy(alpha = 0.5f)),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Column(modifier = Modifier.padding(10.dp)) {
                        Text(
                            text = "SELECTIVE ROUTING INSTRUMENTATION",
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF38BDF8)
                        )
                        Text(
                            text = "Level ${info.escalationLevel} | Router Latency: ${String.format("%.2fms", info.totalRoutingLatencyMs)} | ${info.energyConservationNote}",
                            fontSize = 10.sp,
                            color = Color(0xFF94A3B8),
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
                Spacer(modifier = Modifier.height(10.dp))
            }

            // Expert Execution Waterfall
            Text(text = "ACTIVE EXPERTS & EDGE RUNTIMES", fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = Color(0xFF64748B))
            Spacer(modifier = Modifier.height(6.dp))

            LazyColumn(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                items(expertRuns) { run ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(containerColor = Color(0xFF0F172A).copy(alpha = 0.5f)),
                        shape = RoundedCornerShape(6.dp)
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(8.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column {
                                Text(text = run.expert_id, fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = Color.White)
                                Text(text = "${run.capability.name} • ${run.status.name}", fontSize = 9.sp, color = if (run.status == ExecutionStatus.SUCCESS) Color(0xFF10B981) else Color(0xFF64748B))
                            }
                            Text(text = String.format("%.1f ms", run.latency_ms), fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = Color(0xFF38BDF8))
                        }
                    }
                }
            }
        }
    }

    // Configurable Gateway URL Dialog
    if (showUrlDialog) {
        AlertDialog(
            onDismissRequest = { showUrlDialog = false },
            title = { Text(text = "Gateway Endpoint Settings", color = Color.White) },
            text = {
                Column {
                    Text(text = "Enter backend WebSocket URL:", fontSize = 12.sp, color = Color(0xFF94A3B8))
                    Spacer(modifier = Modifier.height(6.dp))
                    TextField(
                        value = urlInput,
                        onValueChange = { urlInput = it },
                        singleLine = true,
                        colors = TextFieldDefaults.colors(
                            focusedTextColor = Color.White,
                            unfocusedTextColor = Color.White,
                            focusedContainerColor = Color(0xFF0F172A),
                            unfocusedContainerColor = Color(0xFF0F172A)
                        )
                    )
                }
            },
            confirmButton = {
                Button(onClick = {
                    onUpdateServerUrl(urlInput)
                    showUrlDialog = false
                }) {
                    Text("Apply & Reconnect")
                }
            },
            dismissButton = {
                TextButton(onClick = { showUrlDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun CameraPreviewComposable(analyzer: CameraAnalysisService) {
    val lifecycleOwner = LocalLifecycleOwner.current

    AndroidView(
        factory = { ctx ->
            val previewView = PreviewView(ctx)
            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)

            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }

                val imageAnalysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                    .build()
                    .also {
                        it.setAnalyzer(Executors.newSingleThreadExecutor(), analyzer)
                    }

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        CameraSelector.DEFAULT_BACK_CAMERA,
                        preview,
                        imageAnalysis
                    )
                } catch (e: Exception) {
                    Log.e("CameraPreview", "CameraX lifecycle bind failure", e)
                }
            }, ContextCompat.getMainExecutor(ctx))

            previewView
        },
        modifier = Modifier.fillMaxSize()
    )
}
