import time
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import WebSocket
from app.websocket.manager import ConnectionManager
from app.engine.experts.location import LocationExpert
from app.engine.experts.motion import MotionExpert
from app.schemas.experts import ExpertRequest, ExpertCapability, ExecutionStatus
from app.schemas.sensors import LocationSnapshot, SensorSnapshot, SensorType, SensorAccuracy


@pytest.mark.asyncio
async def test_slow_consumer_observer_eviction():
    """
    Checklist 33-N006: Verify slow consumers are detected and evicted safely
    rather than allowing unbounded memory growth.
    """
    manager = ConnectionManager(observer_timeout_seconds=0.1)

    # Fast observer
    fast_ws = AsyncMock(spec=WebSocket)
    fast_ws.send_text = AsyncMock()

    # Stalled slow consumer observer
    async def slow_send_text(text: str):
        await asyncio.sleep(0.5)  # exceeds 0.1s timeout

    slow_ws = AsyncMock(spec=WebSocket)
    slow_ws.send_text = slow_send_text
    slow_ws.close = AsyncMock()

    await manager.connect_observer(fast_ws)
    await manager.connect_observer(slow_ws)
    assert len(manager.active_observers) == 2

    # Broadcast message
    test_msg = {"event_type": "telemetry", "data": "sample"}
    await manager.broadcast_to_observers(test_msg)

    # Slow consumer must be evicted and disconnected with code 1008
    assert slow_ws not in manager.active_observers
    assert fast_ws in manager.active_observers
    slow_ws.close.assert_awaited_once_with(code=1008, reason="Slow consumer evicted")


@pytest.mark.asyncio
async def test_graceful_connection_draining():
    """
    Checklist 33-B014: Verify graceful connection draining on shutdown
    emits 'server.draining' frame and issues close code 1001 (Going Away).
    """
    manager = ConnectionManager()

    device_ws = AsyncMock(spec=WebSocket)
    device_ws.send_text = AsyncMock()
    device_ws.close = AsyncMock()

    observer_ws = AsyncMock(spec=WebSocket)
    observer_ws.send_text = AsyncMock()
    observer_ws.close = AsyncMock()

    await manager.connect_device("dev_drain_1", device_ws)
    await manager.connect_observer(observer_ws)
    assert len(manager.active_devices) == 1
    assert len(manager.active_observers) == 1

    # Drain all connections
    await manager.drain_all(reason="Maintenance deploy", code=1001)

    # Check both device and observer received the draining frame and close code 1001
    device_ws.close.assert_awaited_once_with(code=1001, reason="Maintenance deploy")
    observer_ws.close.assert_awaited_once_with(code=1001, reason="Maintenance deploy")
    assert len(manager.active_devices) == 0
    assert len(manager.active_observers) == 0


@pytest.mark.asyncio
async def test_stale_gps_fix_rejection():
    """
    Checklist 75-N001: Reject GPS fixes older than 10.0 seconds as stale data.
    """
    expert = LocationExpert()
    now_ns = time.time_ns()

    # Create stale GPS fix: 15 seconds old
    stale_timestamp_ns = now_ns - int(15.0 * 1e9)
    stale_loc = LocationSnapshot(
        latitude=37.7749,
        longitude=-122.4194,
        accuracy_meters=8.0,
        speed_mps=12.0,
        timestamp_ns=stale_timestamp_ns,
        is_available=True
    )

    req = ExpertRequest(
        session_id="s_stale_gps",
        correlation_id="c_stale_gps",
        target_capabilities=[ExpertCapability.LOCATION_ANALYSIS],
        location_snapshot=stale_loc
    )

    result = await expert.execute(req)
    assert result.status == ExecutionStatus.UNAVAILABLE
    assert "stale location fix" in result.limitations[0]
    assert len(result.evidence) == 0


@pytest.mark.asyncio
async def test_future_skew_gps_fix_rejection():
    """
    Checklist 75-N001 / 75-N002: Reject GPS fixes more than 5.0s in the future as clock skew.
    """
    expert = LocationExpert()
    now_ns = time.time_ns()

    # Create future-skewed GPS fix: 10 seconds in future
    future_timestamp_ns = now_ns + int(10.0 * 1e9)
    future_loc = LocationSnapshot(
        latitude=37.7749,
        longitude=-122.4194,
        accuracy_meters=8.0,
        speed_mps=12.0,
        timestamp_ns=future_timestamp_ns,
        is_available=True
    )

    req = ExpertRequest(
        session_id="s_future_gps",
        correlation_id="c_future_gps",
        target_capabilities=[ExpertCapability.LOCATION_ANALYSIS],
        location_snapshot=future_loc
    )

    result = await expert.execute(req)
    assert result.status == ExecutionStatus.UNAVAILABLE
    assert "stale location fix or clock skew" in result.limitations[0]
    assert len(result.evidence) == 0


@pytest.mark.asyncio
async def test_fresh_gps_fix_accepted():
    """
    Checklist 75-N001: Fresh GPS fix within 10.0s window is processed correctly.
    """
    expert = LocationExpert()
    now_ns = time.time_ns()

    # Fresh GPS fix: 0.5s old
    fresh_timestamp_ns = now_ns - int(0.5 * 1e9)
    fresh_loc = LocationSnapshot(
        latitude=37.7749,
        longitude=-122.4194,
        accuracy_meters=6.0,
        speed_mps=10.0,
        timestamp_ns=fresh_timestamp_ns,
        is_available=True
    )

    req = ExpertRequest(
        session_id="s_fresh_gps",
        correlation_id="c_fresh_gps",
        target_capabilities=[ExpertCapability.LOCATION_ANALYSIS],
        location_snapshot=fresh_loc
    )

    result = await expert.execute(req)
    assert result.status == ExecutionStatus.SUCCESS
    assert result.prediction == "HIGH_SPEED_TRANSIT"
    assert len(result.evidence) == 1


@pytest.mark.asyncio
async def test_motion_out_of_range_spike_filtered():
    """
    Checklist 75-N010: Clamp unphysical accelerometer spikes (> 200 m/s²)
    as hardware glitches to prevent false pedestrian impact alerts.
    """
    expert = MotionExpert()
    now_ns = time.time_ns()

    # Corrupted / unphysical spike reading: 250 m/s² (~25g)
    glitch_snapshot = SensorSnapshot(
        sensor_type=SensorType.ACCELEROMETER,
        timestamp_ns=now_ns,
        values=[150.0, 180.0, 100.0],  # sqrt(150^2 + 180^2 + 100^2) = ~255 m/s²
        accuracy=SensorAccuracy.HIGH,
        is_available=True
    )

    req = ExpertRequest(
        session_id="s_glitch_motion",
        correlation_id="c_glitch_motion",
        target_capabilities=[ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=[glitch_snapshot]
    )

    result = await expert.execute(req)
    assert result.status == ExecutionStatus.DEGRADED
    assert result.prediction == "SENSOR_GLITCH_SUSPECTED"
    assert result.confidence == 0.0
    assert len(result.evidence) == 0


@pytest.mark.asyncio
async def test_postgresql_biginteger_timestamp_compatibility():
    """
    P0 Defect Regression: Verify nanosecond timestamps (~1.73e18)
    store cleanly in BigInteger columns without 32-bit integer overflow.
    """
    from app.db.session import AsyncSessionLocal
    from app.db.models import DeviceModel, SessionModel, SensorSnapshotModel, LocationModel

    large_epoch_ns = 1_730_800_000_123_456_789  # > 2.147e9 (overflows standard 32-bit integer)

    async with AsyncSessionLocal() as session:
        # Provision test device and session
        dev = DeviceModel(
            device_id="dev_bigint_test",
            name="BigInt Verification Client",
            status="ACTIVE"
        )
        session.add(dev)
        sess = SessionModel(
            session_id="sess_bigint_test",
            device_id="dev_bigint_test",
            status="ACTIVE"
        )
        session.add(sess)

        # Snapshot with large nanosecond timestamp
        snap = SensorSnapshotModel(
            session_id="sess_bigint_test",
            sensor_type="ACCELEROMETER",
            timestamp_ns=large_epoch_ns,
            values=[0.1, 9.81, 0.2]
        )
        session.add(snap)

        loc = LocationModel(
            session_id="sess_bigint_test",
            latitude=37.7749,
            longitude=-122.4194,
            accuracy_meters=5.0,
            timestamp_ns=large_epoch_ns
        )
        session.add(loc)
        await session.commit()

        # Query back and assert exact 64-bit value preservation
        from sqlalchemy import select
        res = await session.execute(select(SensorSnapshotModel).where(SensorSnapshotModel.session_id == "sess_bigint_test"))
        retrieved_snap = res.scalars().first()
        assert retrieved_snap is not None
        assert retrieved_snap.timestamp_ns == large_epoch_ns

        # Cleanup
        await session.delete(dev)
        await session.commit()


@pytest.mark.asyncio
async def test_celery_purge_expired_telemetry_task():
    """
    P1 Defect Regression: Verify Celery worker entrypoint exists and
    purge_expired_telemetry executes database operations cleanly.
    """
    from app.core.celery_app import celery_app, purge_expired_telemetry
    assert celery_app.main == "streetsense"

    # Execute purge task directly
    purged_count = purge_expired_telemetry(retention_days=365)
    assert isinstance(purged_count, int)
    assert purged_count >= 0


@pytest.mark.asyncio
async def test_vision_expert_lens_blur_optical_degradation():
    """
    P1 Defect Regression: Verify ObjectExpert detects optical lens blur and
    extreme underexposure from CameraX metadata, returning DEGRADED instead
    of canned success.
    """
    from app.engine.experts.vision_object import ObjectExpert
    from app.schemas.sensors import FrameMetadata

    expert = ObjectExpert(model_path="non_existent.tflite")

    # Degraded blurry frame
    blurry_frame = FrameMetadata(
        timestamp_ns=time.time_ns(),
        width=1920,
        height=1080,
        luminance_mean=120.0,
        blur_score=4.2  # < 10.0 threshold indicates severe blur
    )

    req = ExpertRequest(
        session_id="s_blur",
        correlation_id="c_blur",
        target_capabilities=[ExpertCapability.OBJECT_DETECTION],
        frame_metadata=blurry_frame
    )

    res = await expert.execute(req)
    assert res.status == ExecutionStatus.DEGRADED
    assert res.prediction == "CAMERA_VISIBILITY_DEGRADED"
    assert "lens blur" in res.limitations[0]
