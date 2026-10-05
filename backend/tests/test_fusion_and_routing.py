import time
import pytest
from app.engine.router import router
from app.engine.fusion import fusion_engine
from app.engine.arbitration import arbitration_engine
from app.engine.reasoning import reasoning_expert
from app.engine.experts.sensor_quality import SensorQualityExpert
from app.engine.experts.motion import MotionExpert
from app.engine.experts.illumination import IlluminationExpert
from app.engine.experts.location import LocationExpert
from app.engine.experts.vision_object import ObjectExpert
from app.schemas.experts import ExpertRequest, ExpertCapability, ExecutionStatus
from app.schemas.sensors import SensorSnapshot, SensorType, SensorAccuracy, LocationSnapshot
from app.schemas.evidence import EvidenceType


@pytest.mark.asyncio
async def test_sensor_quality_expert():
    expert = SensorQualityExpert()
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[0.0, 9.8, 0.0],
            accuracy=SensorAccuracy.HIGH
        ),
        SensorSnapshot(
            sensor_type=SensorType.GYROSCOPE,
            timestamp_ns=time.time_ns(),
            values=[0.0, 0.0, 0.0],
            accuracy=SensorAccuracy.UNRELIABLE
        )
    ]
    req = ExpertRequest(
        session_id="s1",
        correlation_id="c1",
        target_capabilities=[ExpertCapability.SENSOR_QUALITY],
        sensor_snapshots=snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert res.confidence == 0.5  # 1 out of 2 is unreliable
    assert len(res.evidence) == 1


@pytest.mark.asyncio
async def test_motion_expert_fall_detection():
    expert = MotionExpert()
    # High impact spike: x=10, y=30, z=5 -> sqrt(100+900+25) = sqrt(1025) ≈ 32.0 m/s²
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[10.0, 30.0, 5.0],
            accuracy=SensorAccuracy.HIGH
        )
    ]
    req = ExpertRequest(
        session_id="s2",
        correlation_id="c2",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert res.prediction == "PEDESTRIAN_FALL_OR_IMPACT"
    assert len(res.evidence) == 1
    assert res.evidence[0]["evidence_type"] == EvidenceType.PEDESTRIAN_FALL.value


@pytest.mark.asyncio
async def test_illumination_expert_low_light():
    expert = IlluminationExpert()
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.AMBIENT_LIGHT,
            timestamp_ns=time.time_ns(),
            values=[1.5],  # 1.5 lux (dark street/night)
            accuracy=SensorAccuracy.HIGH
        )
    ]
    req = ExpertRequest(
        session_id="s3",
        correlation_id="c3",
        target_capabilities=[ExpertCapability.ILLUMINATION_ANALYSIS],
        sensor_snapshots=snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert res.prediction == "LOW_LIGHT_ENVIRONMENT"
    assert res.evidence[0]["evidence_type"] == EvidenceType.LOW_LIGHT_ENVIRONMENT.value


@pytest.mark.asyncio
async def test_vision_zero_mock_policy():
    # Without model weights file, vision expert MUST return UNAVAILABLE rather than fake detections
    expert = ObjectExpert(model_path="non_existent_weights.tflite")
    assert not expert.is_available()

    req = ExpertRequest(
        session_id="s4",
        correlation_id="c4",
        target_capabilities=[ExpertCapability.OBJECT_DETECTION]
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.UNAVAILABLE
    assert res.confidence == 0.0
    assert len(res.evidence) == 0
    assert any("Zero-Mock Policy" in lim for lim in res.limitations)


@pytest.mark.asyncio
async def test_selective_routing_and_evidence_fusion_flow():
    # High impact motion input
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[12.0, 28.0, 8.0],
            accuracy=SensorAccuracy.HIGH
        ),
        SensorSnapshot(
            sensor_type=SensorType.AMBIENT_LIGHT,
            timestamp_ns=time.time_ns(),
            values=[120.0],
            accuracy=SensorAccuracy.HIGH
        )
    ]
    req = ExpertRequest(
        session_id="s_e2e",
        correlation_id="c_e2e",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS, ExpertCapability.SENSOR_QUALITY],
        sensor_snapshots=snapshots
    )

    # 1. Selective Router executes Level 0 and Level 1
    results, evidence_items = await router.route_and_execute(req)
    assert len(results) >= 2
    assert len(evidence_items) >= 1

    # 2. Conflict Arbitration
    agreement, conflicts, escalation = arbitration_engine.arbitrate(results, evidence_items)
    assert agreement > 0.5
    assert not escalation

    # 3. Multi-Modal Evidence Fusion
    event = fusion_engine.fuse("s_e2e", results, evidence_items, arbitration_agreement=agreement)
    assert event is not None
    assert event.category.value == "PEDESTRIAN_FALL_OR_IMPACT"
    assert event.severity.value == "HIGH_RISK"
    assert event.confidence_breakdown.final_decision_confidence > 0.70

    # 4. Local Reasoning
    explanation = reasoning_expert.generate_explanation(event, evidence_items)
    assert "PEDESTRIAN_FALL_OR_IMPACT" in explanation
    assert "Corroborating Evidence" in explanation


@pytest.mark.asyncio
async def test_motion_normal_gravity_not_kinetic_shock():
    expert = MotionExpert()
    # Baseline Earth gravity 9.81 m/s²
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[0.1, 0.2, 9.81],
            accuracy=SensorAccuracy.HIGH
        )
    ]
    req = ExpertRequest(
        session_id="s_norm",
        correlation_id="c_norm",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert res.prediction == "NORMAL_MOTION"
    assert len(res.evidence) == 0


@pytest.mark.asyncio
async def test_motion_below_24_5_threshold_no_shock():
    expert = MotionExpert()
    # Walking motion: sqrt(10^2 + 12^2 + 10^2) ≈ 18.5 m/s² (< 24.5 m/s²)
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[10.0, 12.0, 10.0],
            accuracy=SensorAccuracy.HIGH
        )
    ]
    req = ExpertRequest(
        session_id="s_walk",
        correlation_id="c_walk",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert res.prediction == "NORMAL_MOTION"
    assert len(res.evidence) == 0


@pytest.mark.asyncio
async def test_motion_spike_and_glitch_rejection():
    expert = MotionExpert()
    # 1722 m/s² spike or NaN values
    spike_snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=time.time_ns(),
            values=[1000.0, 1400.0, 100.0],
            accuracy=SensorAccuracy.HIGH,
            max_range=156.9
        )
    ]
    req = ExpertRequest(
        session_id="s_spike",
        correlation_id="c_spike",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=spike_snapshots
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.DEGRADED
    assert res.prediction == "SENSOR_GLITCH_SUSPECTED"
    assert len(res.evidence) == 0


@pytest.mark.asyncio
async def test_location_sentinel_handling():
    expert = LocationExpert()
    sentinel_loc = LocationSnapshot(
        latitude=0.0,
        longitude=0.0,
        accuracy_meters=999.0,
        timestamp_ns=time.time_ns(),
        is_available=False
    )
    req = ExpertRequest(
        session_id="s_sentinel",
        correlation_id="c_sentinel",
        target_capabilities=[ExpertCapability.LOCATION_ANALYSIS],
        location_snapshot=sentinel_loc
    )
    res = await expert.execute(req)
    assert res.status == ExecutionStatus.UNAVAILABLE
    assert len(res.evidence) == 0
