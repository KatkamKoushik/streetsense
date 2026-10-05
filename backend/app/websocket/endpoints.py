import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.websocket.manager import ws_manager
from app.schemas.transport import WsMessageEnvelope, EventType
from app.db.repositories import (
    TelemetryRepository, ExpertRunRepository, EventRepository, SessionRepository, DeviceRepository
)
from app.schemas.sensors import SensorSnapshot, LocationSnapshot
from app.schemas.experts import ExpertResult
from app.schemas.evidence import EvidenceItem
from app.schemas.events import DetectedEvent
from app.schemas.transport import DeviceStatusPayload

logger = logging.getLogger("streetsense.websocket.endpoints")
router = APIRouter(tags=["websocket"])


async def handle_telemetry_persistence(envelope: WsMessageEnvelope) -> None:
    """Async background persistence of incoming WebSocket telemetry envelope."""
    async with AsyncSessionLocal() as db:
        try:
            event_type = envelope.event_type
            payload = envelope.payload
            session_id = envelope.session_id
            device_id = envelope.device_id

            # Ensure session exists
            sess_repo = SessionRepository(db)
            session = await sess_repo.get_by_id(session_id)
            if not session:
                dev_repo = DeviceRepository(db)
                await dev_repo.register_or_update(device_id=device_id, name=f"Device {device_id[:8]}")
                await sess_repo.start_session(session_id=session_id, device_id=device_id)

            if event_type == EventType.SENSOR_STATUS:
                if "snapshots" in payload:
                    snapshots = [SensorSnapshot(**s) for s in payload["snapshots"]]
                    telemetry_repo = TelemetryRepository(db)
                    await telemetry_repo.save_sensor_snapshots(session_id, snapshots)

            elif event_type in (EventType.EXPERT_COMPLETED, EventType.INFERENCE_COMPLETED):
                if "expert_result" in payload:
                    result = ExpertResult(**payload["expert_result"])
                    expert_repo = ExpertRunRepository(db)
                    run_model = await expert_repo.save_expert_run(session_id, result)
                    if "evidence" in payload and payload["evidence"]:
                        evidence_items = [EvidenceItem(**e) for e in payload["evidence"]]
                        await expert_repo.save_evidence_items(session_id, run_model.run_id, evidence_items)

            elif event_type in (EventType.EVENT_DETECTED, EventType.ALERT_TRIGGERED):
                if "event" in payload:
                    detected_event = DetectedEvent(**payload["event"])
                    event_repo = EventRepository(db)
                    await event_repo.save_event(detected_event)

            elif event_type == EventType.DEVICE_STATUS:
                if "device_status" in payload:
                    status_payload = DeviceStatusPayload(**payload["device_status"])
                    telemetry_repo = TelemetryRepository(db)
                    await telemetry_repo.save_device_health(device_id, status_payload)

        except Exception as e:
            logger.error(f"Error persisting telemetry envelope {envelope.message_id}: {e}", exc_info=True)


@router.websocket("/ws/telemetry")
async def websocket_telemetry_ingress(websocket: WebSocket, device_id: str = "default_device"):
    await ws_manager.connect_device(device_id, websocket)
    try:
        while True:
            text_data = await websocket.receive_text()
            data = json.loads(text_data)
            envelope = WsMessageEnvelope(**data)

            if ws_manager.is_duplicate(envelope.message_id):
                continue

            # Heartbeat handling
            if envelope.event_type == EventType.HEARTBEAT_PING:
                pong = {
                    "message_id": f"pong-{envelope.message_id}",
                    "correlation_id": envelope.correlation_id,
                    "session_id": envelope.session_id,
                    "device_id": envelope.device_id,
                    "timestamp_ns": envelope.timestamp_ns,
                    "event_type": EventType.HEARTBEAT_PONG.value,
                    "sequence_number": envelope.sequence_number,
                    "payload": {"status": "ok"}
                }
                await websocket.send_text(json.dumps(pong))
                continue

            # Broadcast immediately to Office Kit observers for sub-millisecond reaction
            await ws_manager.broadcast_to_observers(envelope.model_dump())

            # Asynchronously persist to database
            await handle_telemetry_persistence(envelope)

    except WebSocketDisconnect:
        ws_manager.disconnect_device(device_id)
    except Exception as e:
        logger.error(f"WebSocket error on device {device_id}: {e}")
        ws_manager.disconnect_device(device_id)


@router.websocket("/ws/office-kit")
async def websocket_office_kit_egress(websocket: WebSocket):
    await ws_manager.connect_observer(websocket)
    try:
        while True:
            # Observer can send ping or commands
            text_data = await websocket.receive_text()
            data = json.loads(text_data)
            if data.get("event_type") == EventType.HEARTBEAT_PING.value:
                pong = {
                    "event_type": EventType.HEARTBEAT_PONG.value,
                    "timestamp_ns": data.get("timestamp_ns", 0),
                    "status": "connected"
                }
                await websocket.send_text(json.dumps(pong))
    except WebSocketDisconnect:
        ws_manager.disconnect_observer(websocket)
    except Exception as e:
        logger.error(f"WebSocket observer error: {e}")
        ws_manager.disconnect_observer(websocket)
