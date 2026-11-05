import time
import json
import pytest
import httpx
import websockets
from app.main import app
from app.core.config import settings
from app.core.security import create_device_token, create_console_token, hash_device_secret
from app.schemas.transport import EventType
from app.db.session import AsyncSessionLocal
from app.db.repositories import DeviceRepository, SessionRepository


@pytest.fixture
def auth_client():
    from starlette.testclient import TestClient
    return TestClient(app)


def test_auth_token_missing_or_invalid_credentials(auth_client):
    # 1. Unknown device
    res = auth_client.post("/api/v1/auth/token", json={"device_id": "nonexistent_device", "api_key": "some_key"})
    assert res.status_code == 401
    assert "Invalid device credentials" in res.json()["detail"]

    # 2. Wrong API key for existing device
    # Provision a test device
    dev_id = f"dev_cred_{int(time.time()*1000)}"
    p = auth_client.post(
        "/api/v1/devices/provision",
        headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY},
        json={"device_id": dev_id, "name": "Cred Test Device"}
    )
    assert p.status_code in (200, 201)

    res2 = auth_client.post("/api/v1/auth/token", json={"device_id": dev_id, "api_key": "wrong_key_12345"})
    assert res2.status_code == 401
    assert "Invalid device credentials" in res2.json()["detail"]


def test_auth_token_revoked_device(auth_client):
    dev_id = f"dev_rev_{int(time.time()*1000)}"
    p = auth_client.post(
        "/api/v1/devices/provision",
        headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY},
        json={"device_id": dev_id, "name": "Revoke Test Device"}
    )
    assert p.status_code in (200, 201)
    secret = p.json().get("device_secret") or p.json()["secret"]

    # Revoke device
    rev_res = auth_client.post(
        f"/api/v1/devices/{dev_id}/revoke",
        headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}
    )
    assert rev_res.status_code == 200

    # Attempt to request token for revoked device
    token_res = auth_client.post("/api/v1/auth/token", json={"device_id": dev_id, "api_key": secret})
    assert token_res.status_code == 403
    assert "revoked" in token_res.json()["detail"].lower()


def test_rest_unauthenticated_requests_rejected(auth_client):
    # 1. Unauthenticated session start
    r1 = auth_client.post("/api/v1/sessions/start", json={"session_id": "s_unauth", "device_id": "d_unauth"})
    assert r1.status_code == 401

    # 2. Unauthenticated batch telemetry
    r2 = auth_client.post("/api/v1/telemetry/batch/s_unauth", json={"session_id": "s_unauth", "snapshots": []})
    assert r2.status_code == 401

    # 3. Unauthenticated device list
    r3 = auth_client.get("/api/v1/devices")
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_websocket_unauthenticated_connection_rejected(live_server):
    ws_url = live_server["ws_url"]
    # Connect without token and send a telemetry frame instead of auth frame
    async with websockets.connect(f"{ws_url}/ws/telemetry") as ws:
        await ws.send(json.dumps({
            "message_id": "m_unauth",
            "correlation_id": "c1",
            "session_id": "s1",
            "device_id": "spoofed_device",
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 1,
            "payload": {}
        }))
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "auth.error"


@pytest.mark.asyncio
async def test_websocket_device_identity_mismatch(live_server):
    ws_url = live_server["ws_url"]
    http_url = live_server["http_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        # Provision dev1 and dev2
        d1 = f"dev_id_1_{int(time.time()*1000)}"
        d2 = f"dev_id_2_{int(time.time()*1000)}"
        p1 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d1, "name": "D1"})
        p2 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d2, "name": "D2"})
        sec1 = p1.json().get("device_secret") or p1.json()["secret"]

        t1_res = await client.post("/api/v1/auth/token", json={"device_id": d1, "api_key": sec1})
        token1 = t1_res.json()["access_token"]

        sess1 = f"sess_mismatch_{int(time.time()*1000)}"
        await client.post("/api/v1/sessions/start", headers={"Authorization": f"Bearer {token1}"}, json={"session_id": sess1, "device_id": d1})

    # Device 1 token used, but envelope claims to be Device 2
    async with websockets.connect(f"{ws_url}/ws/telemetry?token={token1}") as ws:
        ack = json.loads(await ws.recv())
        assert ack["event_type"] == "auth.success"

        envelope = {
            "message_id": f"msg_mismatch_{time.time_ns()}",
            "correlation_id": "corr_mismatch",
            "session_id": sess1,
            "device_id": d2,  # Mismatch with token subject (d1)
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 1,
            "payload": {}
        }
        await ws.send(json.dumps(envelope))
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "error"
        assert resp["code"] == 4403
        assert "Identity mismatch" in resp["error"]


@pytest.mark.asyncio
async def test_websocket_session_ownership_mismatch(live_server):
    ws_url = live_server["ws_url"]
    http_url = live_server["http_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        d1 = f"dev_owner_1_{int(time.time()*1000)}"
        d2 = f"dev_owner_2_{int(time.time()*1000)}"
        p1 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d1, "name": "D1"})
        p2 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d2, "name": "D2"})
        sec1 = p1.json().get("device_secret") or p1.json()["secret"]
        sec2 = p2.json().get("device_secret") or p2.json()["secret"]

        t1_res = await client.post("/api/v1/auth/token", json={"device_id": d1, "api_key": sec1})
        t2_res = await client.post("/api/v1/auth/token", json={"device_id": d2, "api_key": sec2})
        token1 = t1_res.json()["access_token"]
        token2 = t2_res.json()["access_token"]

        sess1 = f"sess_owned_by_d1_{int(time.time()*1000)}"
        await client.post("/api/v1/sessions/start", headers={"Authorization": f"Bearer {token1}"}, json={"session_id": sess1, "device_id": d1})

    # Device 2 tries to send telemetry for Device 1's session
    async with websockets.connect(f"{ws_url}/ws/telemetry?token={token2}") as ws:
        ack = json.loads(await ws.recv())
        assert ack["event_type"] == "auth.success"

        envelope = {
            "message_id": f"msg_sess_mismatch_{time.time_ns()}",
            "correlation_id": "corr_sess_mismatch",
            "session_id": sess1,  # Belongs to d1, not d2
            "device_id": d2,
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.EVENT_DETECTED.value,
            "sequence_number": 1,
            "payload": {
                "event": {
                    "event_id": f"evt_forged_{time.time_ns()}",
                    "session_id": sess1,
                    "timestamp_ns": int(time.time_ns()),
                    "category": "PEDESTRIAN_FALL_OR_IMPACT",
                    "severity": "HIGH_RISK",
                    "confidence_breakdown": {
                        "prediction_confidence": 0.9, "input_quality": 0.9, "temporal_consistency": 0.9,
                        "sensor_reliability": 0.9, "cross_expert_agreement": 0.9, "geometric_consistency": 0.9,
                        "evidence_quality": 0.9, "final_decision_confidence": 0.9
                    },
                    "contributing_evidence_ids": ["ev_1"],
                    "explanation": "Forged event",
                    "haptic_pattern": "STRONG_DOUBLE_PULSE",
                    "is_dismissed": False
                }
            }
        }
        await ws.send(json.dumps(envelope))
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "error"
        assert resp["code"] == 4400
        assert "Session" in resp["error"]


@pytest.mark.asyncio
async def test_websocket_non_monotonic_sequence(live_server):
    ws_url = live_server["ws_url"]
    http_url = live_server["http_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        d1 = f"dev_seq_{int(time.time()*1000)}"
        p1 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d1, "name": "D1"})
        sec1 = p1.json().get("device_secret") or p1.json()["secret"]
        t1_res = await client.post("/api/v1/auth/token", json={"device_id": d1, "api_key": sec1})
        token1 = t1_res.json()["access_token"]
        sess1 = f"sess_seq_{int(time.time()*1000)}"
        await client.post("/api/v1/sessions/start", headers={"Authorization": f"Bearer {token1}"}, json={"session_id": sess1, "device_id": d1})

    async with websockets.connect(f"{ws_url}/ws/telemetry?token={token1}") as ws:
        ack = json.loads(await ws.recv())
        assert ack["event_type"] == "auth.success"

        # Message 1 with sequence 10
        env1 = {
            "message_id": f"msg_seq_10_{time.time_ns()}",
            "correlation_id": "corr_seq",
            "session_id": sess1,
            "device_id": d1,
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 10,
            "payload": {}
        }
        await ws.send(json.dumps(env1))
        resp1 = json.loads(await ws.recv())
        assert resp1["event_type"] == EventType.HEARTBEAT_PONG.value

        # Message 2 with sequence 5 (regression / replay)
        env2 = {
            "message_id": f"msg_seq_5_{time.time_ns()}",
            "correlation_id": "corr_seq",
            "session_id": sess1,
            "device_id": d1,
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 5,
            "payload": {}
        }
        await ws.send(json.dumps(env2))
        resp2 = json.loads(await ws.recv())
        assert resp2["event_type"] == "error"
        assert resp2["code"] == 4409
        assert "monotonic" in resp2["error"]


@pytest.mark.asyncio
async def test_websocket_excessive_timestamp_skew(live_server):
    ws_url = live_server["ws_url"]
    http_url = live_server["http_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        d1 = f"dev_skew_{int(time.time()*1000)}"
        p1 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d1, "name": "D1"})
        sec1 = p1.json().get("device_secret") or p1.json()["secret"]
        t1_res = await client.post("/api/v1/auth/token", json={"device_id": d1, "api_key": sec1})
        token1 = t1_res.json()["access_token"]
        sess1 = f"sess_skew_{int(time.time()*1000)}"
        await client.post("/api/v1/sessions/start", headers={"Authorization": f"Bearer {token1}"}, json={"session_id": sess1, "device_id": d1})

    async with websockets.connect(f"{ws_url}/ws/telemetry?token={token1}") as ws:
        ack = json.loads(await ws.recv())
        assert ack["event_type"] == "auth.success"

        # Timestamp from 1 hour ago (3600 seconds)
        skewed_time_ns = int((time.time() - 3600) * 1e9)
        env = {
            "message_id": f"msg_skew_{time.time_ns()}",
            "correlation_id": "corr_skew",
            "session_id": sess1,
            "device_id": d1,
            "timestamp_ns": skewed_time_ns,
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 100,
            "payload": {}
        }
        await ws.send(json.dumps(env))
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "error"
        assert resp["code"] == 4400
        assert "Timestamp skew" in resp["error"]


@pytest.mark.asyncio
async def test_websocket_oversized_message_rejected(live_server):
    ws_url = live_server["ws_url"]
    http_url = live_server["http_url"]

    async with httpx.AsyncClient(base_url=http_url) as client:
        d1 = f"dev_huge_{int(time.time()*1000)}"
        p1 = await client.post("/api/v1/devices/provision", headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}, json={"device_id": d1, "name": "D1"})
        sec1 = p1.json().get("device_secret") or p1.json()["secret"]
        t1_res = await client.post("/api/v1/auth/token", json={"device_id": d1, "api_key": sec1})
        token1 = t1_res.json()["access_token"]
        sess1 = f"sess_huge_{int(time.time()*1000)}"
        await client.post("/api/v1/sessions/start", headers={"Authorization": f"Bearer {token1}"}, json={"session_id": sess1, "device_id": d1})

    async with websockets.connect(f"{ws_url}/ws/telemetry?token={token1}") as ws:
        ack = json.loads(await ws.recv())
        assert ack["event_type"] == "auth.success"

        # Create a payload exceeding 64KB (e.g. 70,000 bytes)
        huge_string = "X" * 70000
        env = {
            "message_id": f"msg_huge_{time.time_ns()}",
            "correlation_id": "corr_huge",
            "session_id": sess1,
            "device_id": d1,
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 200,
            "payload": {"data": huge_string}
        }
        await ws.send(json.dumps(env))
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "error"
        assert resp["code"] == 4413
        assert "exceeds" in resp["error"]


@pytest.mark.asyncio
async def test_console_unauthorized_observer_rejected(live_server):
    ws_url = live_server["ws_url"]
    dev_token = create_device_token("dev_unauth_observer")

    # Connecting to /ws/console with a DEVICE token (which lacks 'console:observe' scope and has device audience)
    async with websockets.connect(f"{ws_url}/ws/console?token={dev_token}") as ws:
        resp = json.loads(await ws.recv())
        assert resp["event_type"] == "auth.error"
        assert "Invalid or expired authentication token" in resp["error"]


@pytest.mark.asyncio
async def test_ready_probe_database_disconnect_returns_503(monkeypatch):
    from starlette.testclient import TestClient
    client = TestClient(app)

    # Normal state should be 200
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
    assert res.json()["database"] == "connected"

    # Simulate database failure by patching AsyncSessionLocal to raise an exception
    class BrokenSession:
        async def __aenter__(self):
            raise ConnectionRefusedError("Simulated database unreachable")
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    import app.main as main_module
    monkeypatch.setattr(main_module, "AsyncSessionLocal", lambda: BrokenSession())

    fail_res = client.get("/ready")
    assert fail_res.status_code == 503
    assert fail_res.json()["status"] == "not_ready"
    assert fail_res.json()["database"] == "disconnected"
