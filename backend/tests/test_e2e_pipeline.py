import time
import json
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.engine.router import router
from app.engine.arbitration import arbitration_engine
from app.engine.fusion import fusion_engine
from app.engine.reasoning import reasoning_expert
from app.schemas.sensors import SensorSnapshot, SensorType, SensorAccuracy
from app.schemas.experts import ExpertRequest, ExpertCapability
from app.schemas.transport import WsMessageEnvelope, EventType
from app.db.session import AsyncSessionLocal
from app.db.repositories import EventRepository, SessionRepository, DeviceRepository


@pytest.mark.asyncio
async def test_complete_vertical_slice_pipeline():
    session_id = f"sess_e2e_{int(time.time())}"
    device_id = "pixel_8_pro_edge"
    now_ns = time.time_ns()

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

    # STEP 6: Transport via WebSocket to Backend & Real-Time Broadcast to Office Kit Console
    client = TestClient(app)
    with client.websocket_connect("/ws/office-kit") as observer_ws:
        with client.websocket_connect(f"/ws/telemetry?device_id={device_id}") as device_ws:
            envelope = WsMessageEnvelope(
                message_id=f"msg_{now_ns}",
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
            device_ws.send_text(json.dumps(envelope.model_dump()))

            # Observer receives broadcast live
            received_raw = observer_ws.receive_text()
            received_msg = json.loads(received_raw)
            assert received_msg["event_type"] == EventType.EVENT_DETECTED.value
            assert received_msg["payload"]["event"]["category"] == "PEDESTRIAN_FALL_OR_IMPACT"
            assert received_msg["payload"]["event"]["severity"] == "HIGH_RISK"

            # Allow server task to complete async DB persistence before disconnect
            time.sleep(0.2)

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
