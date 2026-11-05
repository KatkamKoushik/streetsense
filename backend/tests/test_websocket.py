import pytest
import json
import time
import httpx
import websockets
from app.schemas.transport import EventType
from app.core.config import settings


@pytest.mark.asyncio
async def test_websocket_first_frame_auth_and_ping_pong(live_server):
    http_url = live_server["http_url"]
    ws_url = live_server["ws_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        # 1. Provision device
        dev_id = f"test_dev_ws1_{int(time.time()*1000)}"
        prov_res = await client.post(
            "/api/v1/devices/provision",
            headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY},
            json={"device_id": dev_id, "name": "WebSocket Handshake Test Device"}
        )
        assert prov_res.status_code in (200, 201)
        dev_secret = prov_res.json().get("device_secret") or prov_res.json()["secret"]

        # 2. Get device token
        token_res = await client.post(
            "/api/v1/auth/token",
            json={"device_id": dev_id, "api_key": dev_secret}
        )
        assert token_res.status_code == 200
        dev_token = token_res.json()["access_token"]

        # 3. Start session
        sess_id = f"sess_ws1_{int(time.time()*1000)}"
        start_res = await client.post(
            "/api/v1/sessions/start",
            headers={"Authorization": f"Bearer {dev_token}"},
            json={"session_id": sess_id, "device_id": dev_id}
        )
        assert start_res.status_code == 200

    # 4. Connect over real WebSocket and perform first-frame authentication
    async with websockets.connect(f"{ws_url}/ws/telemetry") as ws:
        # Step A: Send auth envelope
        await ws.send(json.dumps({
            "event_type": "auth",
            "token": dev_token
        }))
        auth_ack = json.loads(await ws.recv())
        assert auth_ack["event_type"] == "auth.success"
        assert auth_ack["subject"] == dev_id

        # Step B: Send heartbeat ping
        ping_envelope = {
            "message_id": "msg_ping_001",
            "correlation_id": "corr_001",
            "session_id": sess_id,
            "device_id": dev_id,
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 1,
            "payload": {}
        }
        await ws.send(json.dumps(ping_envelope))
        pong = json.loads(await ws.recv())
        assert pong["event_type"] == EventType.HEARTBEAT_PONG.value
        assert pong["message_id"] == "pong-msg_ping_001"


@pytest.mark.asyncio
async def test_websocket_query_auth_and_telemetry_broadcast(live_server):
    http_url = live_server["http_url"]
    ws_url = live_server["ws_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        # 1. Provision device
        dev_id = f"test_dev_ws2_{int(time.time()*1000)}"
        prov_res = await client.post(
            "/api/v1/devices/provision",
            headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY},
            json={"device_id": dev_id, "name": "WebSocket Broadcast Test Device"}
        )
        assert prov_res.status_code in (200, 201)
        dev_secret = prov_res.json().get("device_secret") or prov_res.json()["secret"]

        # 2. Get device token
        token_res = await client.post(
            "/api/v1/auth/token",
            json={"device_id": dev_id, "api_key": dev_secret}
        )
        assert token_res.status_code == 200
        dev_token = token_res.json()["access_token"]

        # 3. Get console token
        console_res = await client.post(
            "/api/v1/auth/console-token",
            headers={"X-Console-Key": settings.CONSOLE_API_KEY}
        )
        assert console_res.status_code == 200
        console_token = console_res.json()["access_token"]

        # 4. Start session
        sess_id = f"sess_ws2_{int(time.time()*1000)}"
        start_res = await client.post(
            "/api/v1/sessions/start",
            headers={"Authorization": f"Bearer {dev_token}"},
            json={"session_id": sess_id, "device_id": dev_id}
        )
        assert start_res.status_code == 200

    # 5. Connect observer and device over real WebSockets
    async with websockets.connect(f"{ws_url}/ws/console?token={console_token}") as obs_ws:
        obs_auth = json.loads(await obs_ws.recv())
        assert obs_auth["event_type"] == "auth.success"

        async with websockets.connect(f"{ws_url}/ws/telemetry?token={dev_token}") as dev_ws:
            dev_auth = json.loads(await dev_ws.recv())
            assert dev_auth["event_type"] == "auth.success"

            event_envelope = {
                "message_id": f"event_msg_ws_{time.time_ns()}",
                "correlation_id": "corr_broadcast_1",
                "session_id": sess_id,
                "device_id": dev_id,
                "timestamp_ns": int(time.time_ns()),
                "event_type": EventType.EVENT_DETECTED.value,
                "sequence_number": 1,
                "payload": {
                    "event": {
                        "event_id": f"evt_broadcast_{time.time_ns()}",
                        "session_id": sess_id,
                        "timestamp_ns": int(time.time_ns()),
                        "category": "PEDESTRIAN_FALL_OR_IMPACT",
                        "severity": "HIGH_RISK",
                        "confidence_breakdown": {
                            "prediction_confidence": 0.92,
                            "input_quality": 0.95,
                            "temporal_consistency": 0.88,
                            "sensor_reliability": 0.99,
                            "cross_expert_agreement": 0.90,
                            "geometric_consistency": 0.85,
                            "evidence_quality": 0.92,
                            "final_decision_confidence": 0.91
                        },
                        "contributing_evidence_ids": ["ev_1", "ev_2"],
                        "explanation": "High kinetic deceleration spike detected by MotionExpert.",
                        "haptic_pattern": "STRONG_DOUBLE_PULSE",
                        "is_dismissed": False
                    }
                }
            }
            # Device sends event
            await dev_ws.send(json.dumps(event_envelope))

            # Observer receives broadcast live
            received_raw = await obs_ws.recv()
            received = json.loads(received_raw)
            assert received["message_id"] == event_envelope["message_id"]
            assert received["event_type"] == EventType.EVENT_DETECTED.value
            assert received["payload"]["event"]["category"] == "PEDESTRIAN_FALL_OR_IMPACT"
            assert received["payload"]["event"]["severity"] == "HIGH_RISK"
