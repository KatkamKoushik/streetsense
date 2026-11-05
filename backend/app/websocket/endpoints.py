import json
import time
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import decode_and_verify_token, redact_location
from app.db.session import AsyncSessionLocal
from app.websocket.manager import ws_manager
from app.schemas.transport import WsMessageEnvelope, EventType, DeviceStatusPayload
from app.schemas.sensors import SensorSnapshot, LocationSnapshot
from app.schemas.experts import ExpertResult
from app.schemas.evidence import EvidenceItem
from app.schemas.events import DetectedEvent
from app.db.repositories import (
    TelemetryRepository, ExpertRunRepository, EventRepository, SessionRepository, DeviceRepository
)
from app.db.models import DeviceModel

logger = logging.getLogger("streetsense.websocket.endpoints")
router = APIRouter(tags=["websocket"])

ALLOWED_TELEMETRY_EVENT_TYPES = {
    EventType.SENSOR_STATUS.value,
    EventType.DEVICE_STATUS.value,
    EventType.EXPERT_COMPLETED.value,
    EventType.INFERENCE_COMPLETED.value,
    EventType.EVENT_DETECTED.value,
    EventType.ALERT_TRIGGERED.value,
    EventType.HEARTBEAT_PING.value,
}


async def authenticate_ws(
    websocket: WebSocket,
    expected_audience: str,
    required_scope: str
) -> Tuple[str, Dict[str, Any], Optional[DeviceModel]]:
    """
    Authenticate a WebSocket connection before accepting ingress.
    Supports:
    1. Sec-WebSocket-Protocol / Authorization header (preferred)
    2. Query param ?token= (scrubbed immediately)
    3. First-frame JSON handshake: {"event_type": "auth", "token": "..."} within timeout window.
    """
    token: Optional[str] = None

    # Check headers
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()

    # Check subprotocol: 'bearer.<token>' or 'bearer, <token>'
    if not token:
        sec_protocol = websocket.headers.get("sec-websocket-protocol")
        if sec_protocol:
            for part in sec_protocol.split(","):
                part = part.strip()
                if part.startswith("bearer."):
                    token = part[7:].strip()
                    break

    # Check query param (fallback for web browsers that cannot set headers)
    if not token and "token" in websocket.query_params:
        token = websocket.query_params["token"]

    await websocket.accept()

    # If not provided in handshake headers/query, wait for first-frame auth
    if not token:
        try:
            auth_raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=settings.WS_AUTH_TIMEOUT_SECONDS
            )
            auth_data = json.loads(auth_raw)
            if auth_data.get("event_type") == "auth":
                token = auth_data.get("token")
        except asyncio.TimeoutError:
            logger.warning("WebSocket auth timeout: no auth frame received within timeout window.")
            await websocket.send_text(json.dumps({
                "event_type": "auth.error",
                "error": "Authentication timed out. First message must be auth envelope."
            }))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=4401)
        except Exception as e:
            logger.warning(f"Malformed auth frame: {e}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=4400)

    if not token:
        await websocket.send_text(json.dumps({
            "event_type": "auth.error",
            "error": "Missing authentication credentials."
        }))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=4401)

    # Cryptographically verify token
    try:
        claims = decode_and_verify_token(
            token=token,
            expected_audience=expected_audience,
            required_scope=required_scope
        )
    except Exception as e:
        logger.warning(f"WebSocket token validation failed: {e}")
        await websocket.send_text(json.dumps({
            "event_type": "auth.error",
            "error": "Invalid or expired authentication token",
            "detail": str(e)
        }))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketDisconnect(code=4401)

    subject = claims.get("sub", "")
    device_obj: Optional[DeviceModel] = None

    # For device telemetry: confirm device is registered and status == ACTIVE
    if expected_audience == settings.JWT_AUDIENCE_DEVICE:
        device_id = claims.get("device_id") or subject
        async with AsyncSessionLocal() as db:
            dev_repo = DeviceRepository(db)
            device_obj = await dev_repo.get_by_id(device_id)

        if not device_obj:
            logger.warning(f"WebSocket rejected: Device '{device_id}' does not exist in registry.")
            await websocket.send_text(json.dumps({
                "event_type": "auth.error",
                "error": f"Device '{device_id}' is not registered."
            }))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=4401)

        if not device_obj.is_active or device_obj.status != "ACTIVE":
            logger.warning(f"WebSocket rejected: Device '{device_id}' is deactivated or revoked ({device_obj.status}).")
            await websocket.send_text(json.dumps({
                "event_type": "auth.error",
                "error": f"Device '{device_id}' access has been revoked or suspended."
            }))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise WebSocketDisconnect(code=4403)

    # Acknowledge successful authentication
    await websocket.send_text(json.dumps({
        "event_type": "auth.success",
        "status": "authenticated",
        "subject": subject
    }))

    return subject, claims, device_obj


async def handle_telemetry_persistence(envelope: WsMessageEnvelope, authenticated_device_id: str) -> None:
    """
    Transactional persistence of incoming validated telemetry envelope.
    Does NOT auto-register unknown devices or sessions.
    """
    async with AsyncSessionLocal() as db:
        try:
            event_type = envelope.event_type
            payload = envelope.payload
            session_id = envelope.session_id

            # Verify session exists and belongs to authenticated device
            sess_repo = SessionRepository(db)
            session = await sess_repo.get_by_id(session_id)
            if not session or session.device_id != authenticated_device_id:
                raise ValueError(
                    f"Session '{session_id}' not found or does not belong to device '{authenticated_device_id}'"
                )

            if event_type == EventType.SENSOR_STATUS:
                if "snapshots" in payload and payload["snapshots"]:
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
                    if detected_event.session_id != session_id:
                        raise ValueError("DetectedEvent session_id mismatch")
                    event_repo = EventRepository(db)
                    await event_repo.save_event(detected_event)

            elif event_type == EventType.DEVICE_STATUS:
                if "device_status" in payload:
                    status_payload = DeviceStatusPayload(**payload["device_status"])
                    telemetry_repo = TelemetryRepository(db)
                    await telemetry_repo.save_device_health(authenticated_device_id, status_payload)

        except Exception as e:
            logger.error(f"Persistence error on message {envelope.message_id} from {authenticated_device_id}: {e}")
            raise e


@router.websocket("/ws/telemetry")
async def websocket_telemetry_ingress(websocket: WebSocket):
    """
    Authenticated telemetry ingress endpoint.
    Strictly verifies identity, bound device_id, session ownership, sequence monotonicity,
    message size, and clock skew. Never accepts unauthenticated frames.
    """
    try:
        subject, claims, device_obj = await authenticate_ws(
            websocket=websocket,
            expected_audience=settings.JWT_AUDIENCE_DEVICE,
            required_scope="device:telemetry"
        )
    except WebSocketDisconnect:
        return

    authenticated_device_id = device_obj.device_id if device_obj else subject
    await ws_manager.connect_device(authenticated_device_id, websocket)

    try:
        while True:
            text_data = await websocket.receive_text()

            # 1. Message Size Guardrail (Application-level)
            byte_length = len(text_data.encode("utf-8"))
            if byte_length > settings.MAX_WS_MESSAGE_SIZE:
                logger.warning(
                    f"Message size {byte_length} exceeds limit {settings.MAX_WS_MESSAGE_SIZE} from {authenticated_device_id}."
                )
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4413,
                    "error": f"Payload size {byte_length} bytes exceeds 64KB ceiling"
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            # 2. Rate Limiting Check
            if not ws_manager.check_rate_limit(authenticated_device_id, settings.WS_RATE_LIMIT_PER_MINUTE):
                logger.warning(f"Rate limit exceeded for device {authenticated_device_id}.")
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4429,
                    "error": "Rate limit exceeded. Maximum 1200 messages/minute."
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            # 3. JSON Parsing & Schema Validation
            try:
                data = json.loads(text_data)
                envelope = WsMessageEnvelope(**data)
                logger.info(f"Parsed envelope {envelope.message_id} of type {envelope.event_type} from {authenticated_device_id}")
            except Exception as e:
                logger.warning(f"Invalid message format from {authenticated_device_id}: {e}")
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4400,
                    "error": "Malformed envelope or invalid schema"
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            # 4. Deduplication
            if ws_manager.is_duplicate(envelope.message_id):
                logger.info(f"Dropped duplicate message {envelope.message_id} from {authenticated_device_id}.")
                continue

            # 5. Event Allowlist
            if envelope.event_type.value not in ALLOWED_TELEMETRY_EVENT_TYPES:
                logger.warning(f"Forbidden event type '{envelope.event_type.value}' from {authenticated_device_id}.")
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4403,
                    "error": f"Event type '{envelope.event_type.value}' is not permitted"
                }))
                continue

            # 6. Device Identity Binding
            if envelope.device_id != authenticated_device_id:
                logger.error(
                    f"IDENTITY SPOOFING DETECTED: Authenticated device '{authenticated_device_id}' "
                    f"sent envelope with mismatched device_id '{envelope.device_id}'."
                )
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4403,
                    "error": "Identity mismatch: envelope device_id does not match authenticated token subject"
                }))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                break

            # 7. Timestamp Skew Window
            now_ns = time.time_ns()
            max_skew_ns = settings.MAX_TIMESTAMP_SKEW_SECONDS * 1_000_000_000
            if abs(now_ns - envelope.timestamp_ns) > max_skew_ns:
                logger.warning(
                    f"Timestamp skew rejected from {authenticated_device_id}: delta {abs(now_ns - envelope.timestamp_ns) / 1e9:.1f}s > {settings.MAX_TIMESTAMP_SKEW_SECONDS}s"
                )
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4400,
                    "error": f"Timestamp skew exceeds {settings.MAX_TIMESTAMP_SKEW_SECONDS} seconds"
                }))
                continue

            # 8. Strictly Monotonic Sequence Numbers
            if not ws_manager.validate_and_update_sequence(envelope.session_id, envelope.sequence_number):
                logger.warning(
                    f"Sequence order error: seq {envelope.sequence_number} on session {envelope.session_id} rejected."
                )
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4409,
                    "error": "Sequence number must be strictly monotonic and greater than prior seen sequence"
                }))
                continue

            # 9. Heartbeat Ping / Pong
            if envelope.event_type == EventType.HEARTBEAT_PING:
                pong = {
                    "message_id": f"pong-{envelope.message_id}",
                    "correlation_id": envelope.correlation_id,
                    "session_id": envelope.session_id,
                    "device_id": authenticated_device_id,
                    "timestamp_ns": time.time_ns(),
                    "event_type": EventType.HEARTBEAT_PONG.value,
                    "sequence_number": envelope.sequence_number,
                    "payload": {"status": "ok"}
                }
                await websocket.send_text(json.dumps(pong))
                continue

            # 10. Transactional Persistence (must pass before broadcast)
            try:
                await handle_telemetry_persistence(envelope, authenticated_device_id)
            except Exception as e:
                logger.error(f"Persistence rejected envelope {envelope.message_id}: {e}")
                await websocket.send_text(json.dumps({
                    "event_type": "error",
                    "code": 4400,
                    "error": f"Persistence failed: {str(e)}"
                }))
                continue

            # 11. Broadcast to Authenticated Observers
            await ws_manager.broadcast_to_observers(envelope.model_dump())

    except WebSocketDisconnect:
        ws_manager.disconnect_device(authenticated_device_id)
    except Exception as e:
        logger.error(f"WebSocket connection error on device {authenticated_device_id}: {e}")
        ws_manager.disconnect_device(authenticated_device_id)


@router.websocket("/ws/console")
async def websocket_console_egress(websocket: WebSocket):
    """
    Authenticated observation console egress endpoint.
    Requires valid token with 'streetsense:console' audience and 'console:observe' scope.
    Never broadcasts to unauthenticated observers.
    """
    try:
        subject, claims, _ = await authenticate_ws(
            websocket=websocket,
            expected_audience=settings.JWT_AUDIENCE_CONSOLE,
            required_scope="console:observe"
        )
    except WebSocketDisconnect:
        return

    await ws_manager.connect_observer(websocket)

    try:
        while True:
            text_data = await websocket.receive_text()
            data = json.loads(text_data)
            if data.get("event_type") == EventType.HEARTBEAT_PING.value:
                pong = {
                    "event_type": EventType.HEARTBEAT_PONG.value,
                    "timestamp_ns": data.get("timestamp_ns", time.time_ns()),
                    "status": "connected"
                }
                await websocket.send_text(json.dumps(pong))
    except WebSocketDisconnect:
        ws_manager.disconnect_observer(websocket)
    except Exception as e:
        logger.error(f"Console observer socket error for {subject}: {e}")
        ws_manager.disconnect_observer(websocket)
