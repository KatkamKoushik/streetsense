import time
import json
import pytest
import websockets
from app.engine.router import router
from app.engine.arbitration import arbitration_engine
from app.engine.fusion import fusion_engine
from app.engine.reasoning import reasoning_expert
from app.schemas.sensors import SensorSnapshot, SensorType, SensorAccuracy
from app.schemas.experts import ExpertRequest, ExpertCapability
from app.schemas.transport import WsMessageEnvelope, EventType
from app.db.session import AsyncSessionLocal
from app.db.repositories import EventRepository, SessionRepository, DeviceRepository
from app.core.security import create_device_token, create_console_token, hash_device_secret
from app.core.config import settings


@pytest.mark.asyncio
async def test_complete_vertical_slice_pipeline(live_server):
    ws_url = live_server["ws_url"]
    session_id = f"sess_e2e_{int(time.time()*1000)}"
    device_id = f"pixel_8_pro_edge_{int(time.time()*1000)}"
    now_ns = time.time_ns()

    # STEP 0: Provision Device and Session in DB
    raw_secret = "test-e2e-device-secret-key-32chars!"
    async with AsyncSessionLocal() as db:
        dev_repo = DeviceRepository(db)
        await dev_repo.provision_device(
            device_id=device_id,
            name="Pixel 8 Pro Test Edge",
            secret=raw_secret
        )
        sess_repo = SessionRepository(db)
        await sess_repo.start_session(session_id=session_id, device_id=device_id)

    device_token = create_device_token(device_id)
    console_token = create_console_token()

    # STEP 1: Real Hardware Sensor Readings
    # Normal walking baseline followed by sudden impact / fall shock
    snapshots = [
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=now_ns - 200_000_000,
            values=[0.5, 9.8, 1.2],
            accuracy=SensorAccuracy.HIGH
        ),
        SensorSnapshot(
            sensor_type=SensorType.ACCELEROMETER,
            timestamp_ns=now_ns - 100_000_000,
            values=[12.0, 28.5, 9.2],  # Severe impact: sqrt(144 + 812.25 + 84.64) = 32.26 m/s² (~3.3g)
            accuracy=SensorAccuracy.HIGH
        ),
        SensorSnapshot(
            sensor_type=SensorType.AMBIENT_LIGHT,
            timestamp_ns=now_ns - 100_000_000,
            values=[450.0],
            accuracy=SensorAccuracy.HIGH
        )
    ]

    # STEP 2: Edge Routing & Selective Expert Execution
    request = ExpertRequest(
        session_id=session_id,
        correlation_id=f"corr_{now_ns}",
        target_capabilities=[ExpertCapability.SENSOR_QUALITY, ExpertCapability.MOTION_ANALYSIS],
        sensor_snapshots=snapshots
    )

    results, evidence_items = await router.route_and_execute(request)
    assert len(results) >= 2
    assert any(e.evidence_type.value == "PEDESTRIAN_FALL" for e in evidence_items)

    # STEP 3: Conflict Arbitration
    agreement, conflicts, escalation = arbitration_engine.arbitrate(results, evidence_items)
    assert agreement > 0.70
    assert not escalation

    # STEP 4: Multi-Modal Evidence Fusion
    detected_event = fusion_engine.fuse(
        session_id=session_id,
        results=results,
        evidence_items=evidence_items,
        arbitration_agreement=agreement,
        latitude=37.7749,
        longitude=-122.4194
    )
    assert detected_event is not None
    assert detected_event.category.value == "PEDESTRIAN_FALL_OR_IMPACT"
    assert detected_event.severity.value == "HIGH_RISK"
    assert detected_event.confidence_breakdown.final_decision_confidence >= 0.75

    # STEP 5: Local Reasoning
    explanation = reasoning_expert.generate_explanation(detected_event, evidence_items)
    assert "PEDESTRIAN_FALL_OR_IMPACT" in explanation
    assert "Corroborating Evidence" in explanation

    # STEP 6: Transport via Authenticated WebSocket to Live Server & Real-Time Broadcast to Web Console
    async with websockets.connect(f"{ws_url}/ws/console?token={console_token}") as observer_ws:
        obs_auth = json.loads(await observer_ws.recv())
        assert obs_auth["event_type"] == "auth.success"

        async with websockets.connect(f"{ws_url}/ws/telemetry?token={device_token}") as device_ws:
            dev_auth = json.loads(await device_ws.recv())
            assert dev_auth["event_type"] == "auth.success"

            envelope = WsMessageEnvelope(
                message_id=f"msg_e2e_{now_ns}",
                correlation_id=request.correlation_id,
                session_id=session_id,
                device_id=device_id,
                timestamp_ns=now_ns,
                event_type=EventType.EVENT_DETECTED,
                sequence_number=1,
                payload={
                    "event": detected_event.model_dump()
                }
            )

            # Device sends to gateway
            await device_ws.send(json.dumps(envelope.model_dump()))

            # Observer receives broadcast live
            received_raw = await observer_ws.recv()
            received_msg = json.loads(received_raw)
            assert received_msg["event_type"] == EventType.EVENT_DETECTED.value
            assert received_msg["payload"]["event"]["category"] == "PEDESTRIAN_FALL_OR_IMPACT"
            assert received_msg["payload"]["event"]["severity"] == "HIGH_RISK"

    # STEP 7: Verify Database Persistence
    async with AsyncSessionLocal() as db:
        event_repo = EventRepository(db)
        events = await event_repo.list_recent_events(session_id=session_id)
        assert len(events) >= 1
        persisted = events[0]
        assert persisted.category == "PEDESTRIAN_FALL_OR_IMPACT"
        assert persisted.severity == "HIGH_RISK"
        assert persisted.latitude == 37.7749
        assert persisted.longitude == -122.4194
