package io.streetsense.engine

import io.streetsense.domain.model.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class OnDeviceEngineTest {

    // TEST 1: Normal gravity-inclusive accelerometer magnitude around 9.8 m/s² must not automatically become a kinetic shock.
    @Test
    fun test1_NormalGravityNotKineticShock() = runBlocking {
        val expert = NativeMotionExpert()
        val nowNs = System.nanoTime()
        // Typical stationary phone: Earth gravity on Z-axis ~9.81 m/s²
        val stationarySnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(0.1f, 0.2f, 9.81f), SensorAccuracy.HIGH)
        )
        val result = expert.execute(stationarySnaps, null, null)
        assertEquals(ExecutionStatus.SUCCESS, result.status)
        assertEquals("NORMAL_MOTION", result.prediction)
        assertTrue("Normal 9.8 m/s² gravity must not produce shock evidence", result.evidence.isEmpty())
    }

    // TEST 2: Validated acceleration below 24.5 m/s² -> no Level 2 escalation.
    @Test
    fun test2_AccelerationBelowThresholdNoLevel2Escalation() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()
        // Walking/jogging: mag = sqrt(10^2 + 12^2 + 10^2) = sqrt(344) ≈ 18.5 m/s² (< 24.5 m/s²)
        val walkingSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(10.0f, 12.0f, 10.0f), SensorAccuracy.HIGH)
        )
        val (results, instrumentation) = router.routeAndEvaluate(walkingSnaps, null, null)
        assertEquals(0, instrumentation.escalationLevel)
        assertEquals(2, results.size) // Quality + Motion only
        assertTrue("Level 0 must report skipped specialists", instrumentation.skippedExperts.isNotEmpty())
    }

    // TEST 3: Validated acceleration >= 24.5 m/s² -> kinetic shock evidence + Level 2 escalation.
    @Test
    fun test3_AccelerationAboveThresholdEscalatesToLevel2() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()
        // High impact: mag = sqrt(12^2 + 22^2 + 6^2) = sqrt(664) ≈ 25.77 m/s² (>= 24.5 m/s²)
        val shockSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(12.0f, 22.0f, 6.0f), SensorAccuracy.HIGH)
        )
        val (results, instrumentation) = router.routeAndEvaluate(shockSnaps, null, null)
        assertEquals(2, instrumentation.escalationLevel)
        val motionResult = results.first { it.capability == ExpertCapability.MOTION_ANALYSIS }
        assertEquals(ExecutionStatus.SUCCESS, motionResult.status)
        assertTrue(motionResult.prediction in listOf("HIGH_KINETIC_JERK", "PEDESTRIAN_FALL_OR_IMPACT"))
        assertTrue("Kinetic shock must produce evidence", motionResult.evidence.isNotEmpty())
    }

    // TEST 4: Anomaly state and router state must agree.
    @Test
    fun test4_AnomalyStateAndRouterStateAgreement() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()

        // Case A: Normal motion -> Level 0
        val normalSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(0f, 9.81f, 0f), SensorAccuracy.HIGH)
        )
        val (normResults, normInst) = router.routeAndEvaluate(normalSnaps, null, null)
        val normMotion = normResults.first { it.capability == ExpertCapability.MOTION_ANALYSIS }
        assertEquals("NORMAL_MOTION", normMotion.prediction)
        assertEquals(0, normInst.escalationLevel)

        // Case B: Severe fall -> Level 2
        val fallSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(15.0f, 28.0f, 10.0f), SensorAccuracy.HIGH)
        )
        val (fallResults, fallInst) = router.routeAndEvaluate(fallSnaps, null, null)
        val fallMotion = fallResults.first { it.capability == ExpertCapability.MOTION_ANALYSIS }
        assertEquals("PEDESTRIAN_FALL_OR_IMPACT", fallMotion.prediction)
        assertEquals(2, fallInst.escalationLevel)
    }

    // TEST 5: Level 2 escalation must select available specialists.
    @Test
    fun test5_Level2EscalationSelectsSpecialists() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()
        val shockSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(14.0f, 25.0f, 8.0f), SensorAccuracy.HIGH),
            SensorSnapshot(SensorType.AMBIENT_LIGHT, nowNs, System.currentTimeMillis(), listOf(45.0f), SensorAccuracy.HIGH)
        )
        val loc = LocationSnapshot(37.7749, -122.4194, 10.0, 5.0f, 1.2f, 45f, nowNs, is_available = true)

        val (results, instrumentation) = router.routeAndEvaluate(shockSnaps, loc, null)
        assertEquals(2, instrumentation.escalationLevel)
        val executedCapabilities = results.map { it.capability }
        assertTrue(executedCapabilities.contains(ExpertCapability.LOCATION_ANALYSIS))
        assertTrue(executedCapabilities.contains(ExpertCapability.ILLUMINATION_ANALYSIS))
        assertTrue(executedCapabilities.contains(ExpertCapability.OBJECT_DETECTION))
    }

    // TEST 6: Unavailable ObjectExpert must return UNAVAILABLE, never fake detection.
    @Test
    fun test6_UnavailableObjectExpertReturnsUnavailableNeverFakeDetection() = runBlocking {
        val visionExpert = NativeEdgeVisionExpert(isModelWeightsLoaded = false)
        assertFalse(visionExpert.isAvailable())

        val result = visionExpert.execute(emptyList(), null, null)
        assertEquals(ExecutionStatus.UNAVAILABLE, result.status)
        assertNull("Zero-mock policy: prediction must be null", result.prediction)
        assertEquals(0.0f, result.confidence, 0.001f)
        assertTrue("Zero-mock policy: evidence must be empty", result.evidence.isEmpty())
        assertTrue(result.limitations.any { it.contains("Zero-Mock Policy Enforced") })
    }

    // TEST 7: NaN / Infinity / invalid sensor timestamp -> rejected/degraded.
    @Test
    fun test7_NanInfinityInvalidTimestampRejectedDegraded() = runBlocking {
        val expert = NativeMotionExpert()
        val nowNs = System.nanoTime()

        // Sample with NaN
        val nanSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(Float.NaN, 9.8f, 0f), SensorAccuracy.HIGH)
        )
        val nanResult = expert.execute(nanSnaps, null, null)
        assertEquals(ExecutionStatus.DEGRADED, nanResult.status)
        assertEquals("SENSOR_GLITCH_SUSPECTED", nanResult.prediction)
        assertTrue(nanResult.evidence.isEmpty())

        // Sample with non-positive timestamp
        val timeSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, -100L, System.currentTimeMillis(), listOf(10f, 10f, 10f), SensorAccuracy.HIGH)
        )
        val timeResult = expert.execute(timeSnaps, null, null)
        assertEquals(ExecutionStatus.DEGRADED, timeResult.status)
        assertEquals("SENSOR_GLITCH_SUSPECTED", timeResult.prediction)
    }

    // TEST 8: Out-of-range sensor value -> sensor anomaly/degraded, not blindly trusted.
    @Test
    fun test8_OutOfRangeSensorSpikeRejectedNotBlindlyTrusted() = runBlocking {
        val expert = NativeMotionExpert()
        val nowNs = System.nanoTime()

        // The observed physical device extreme value ~1722 m/s²
        val spikeSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(1000.0f, 1400.0f, 100.0f), SensorAccuracy.HIGH, max_range = 156.9f)
        )
        val spikeResult = expert.execute(spikeSnaps, null, null)
        assertEquals(ExecutionStatus.DEGRADED, spikeResult.status)
        assertEquals("SENSOR_GLITCH_SUSPECTED", spikeResult.prediction)
        assertTrue("Extreme 1722 m/s² spike must NOT create false kinetic shock evidence", spikeResult.evidence.isEmpty())
    }

    // TEST 9: GPS unavailable sentinel -> unavailable GPS evidence, not 999m valid accuracy.
    @Test
    fun test9_GpsUnavailableSentinelReturnsUnavailableEvidence() = runBlocking {
        val expert = NativeLocationExpert()
        val nowNs = System.nanoTime()

        // Sentinel 999.0m
        val sentinelLoc = LocationSnapshot(
            latitude = 0.0,
            longitude = 0.0,
            accuracy_meters = 999.0f,
            timestamp_ns = nowNs,
            is_available = false
        )
        val result = expert.execute(emptyList(), sentinelLoc, null)
        assertEquals(ExecutionStatus.UNAVAILABLE, result.status)
        assertEquals("LOCATION_UNAVAILABLE", result.prediction)
        assertTrue("Sentinel 999m must not produce location evidence", result.evidence.isEmpty())

        // Null accuracy
        val nullLoc = LocationSnapshot(
            latitude = 0.0,
            longitude = 0.0,
            accuracy_meters = null,
            timestamp_ns = nowNs,
            is_available = false
        )
        val nullResult = expert.execute(emptyList(), nullLoc, null)
        assertEquals(ExecutionStatus.UNAVAILABLE, nullResult.status)
    }

    // TEST 10: UI state is derived from authoritative routing result.
    @Test
    fun test10_AuthoritativeRoutingStateDerivation() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()

        // Normal state: level 0, 3 skipped experts
        val normalSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(0f, 9.81f, 0f), SensorAccuracy.HIGH)
        )
        val (_, normalInst) = router.routeAndEvaluate(normalSnaps, null, null)
        assertEquals(0, normalInst.escalationLevel)
        assertEquals(3, normalInst.skippedExperts.size)
        assertTrue(normalInst.energyConservationNote.contains("3 expensive experts skipped"))

        // Escalated state: level 2, 0 skipped experts
        val shockSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(15.0f, 26.0f, 8.0f), SensorAccuracy.HIGH)
        )
        val (_, shockInst) = router.routeAndEvaluate(shockSnaps, null, null)
        assertEquals(2, shockInst.escalationLevel)
        assertEquals(0, shockInst.skippedExperts.size)
    }

    // TEST 11: Normal state reports expensive experts skipped.
    @Test
    fun test11_NormalStateReportsExpensiveExpertsSkipped() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()
        val normalSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(0.1f, 9.8f, 0.2f), SensorAccuracy.HIGH)
        )
        val (_, inst) = router.routeAndEvaluate(normalSnaps, null, null)
        val skippedIds = inst.skippedExperts.map { it.first }
        assertTrue(skippedIds.contains("location_expert_v1"))
        assertTrue(skippedIds.contains("illumination_expert_v1"))
        assertTrue(skippedIds.contains("vision_object_expert_v1"))
    }

    // TEST 12: Escalated state does NOT report those experts as skipped.
    @Test
    fun test12_EscalatedStateDoesNotReportExpertsAsSkipped() = runBlocking {
        val router = NativeSelectiveRouter()
        val nowNs = System.nanoTime()
        val fallSnaps = listOf(
            SensorSnapshot(SensorType.ACCELEROMETER, nowNs, System.currentTimeMillis(), listOf(14.0f, 28.0f, 10.0f), SensorAccuracy.HIGH)
        )
        val (results, inst) = router.routeAndEvaluate(fallSnaps, null, null)
        assertEquals(2, inst.escalationLevel)
        assertTrue("In Level 2 escalation, skippedExperts list must be completely empty", inst.skippedExperts.isEmpty())
        assertFalse("Must not report low-power skipped message", inst.energyConservationNote.contains("expensive experts skipped"))
        assertTrue(inst.selectedExperts.contains("vision_object_expert_v1"))
    }
}
