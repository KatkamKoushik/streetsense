import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.init_db import init_db
from app.core.config import settings


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_health_and_readiness():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

        resp2 = await client.get("/ready")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "ready"
        assert resp2.json()["database"] == "connected"
        assert resp2.json()["schema"] == "verified"


@pytest.mark.asyncio
async def test_device_registration_and_auth_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        device_id = f"dev_test_{uuid.uuid4().hex[:6]}"
        dev_secret = f"sec_test_{uuid.uuid4().hex[:16]}"

        # 1. Provision device with X-Provisioning-Key
        prov_payload = {
            "device_id": device_id,
            "name": "Integration Test Device",
            "model": "Test Phone",
            "device_secret": dev_secret
        }
        resp_prov = await client.post(
            "/api/v1/devices/provision",
            json=prov_payload,
            headers={"X-Provisioning-Key": settings.DEVICE_PROVISIONING_KEY}
        )
        assert resp_prov.status_code == 200
        prov_data = resp_prov.json()
        assert prov_data["device_id"] == device_id
        assert prov_data["is_active"] is True
        assert prov_data["status"] == "ACTIVE"

        # 2. Acquire device telemetry token using the provisioned secret
        auth_resp = await client.post(
            "/api/v1/auth/token",
            json={"device_id": device_id, "device_secret": dev_secret}
        )
        assert auth_resp.status_code == 200
        auth_data = auth_resp.json()
        assert "access_token" in auth_data
        assert auth_data["token_type"] == "bearer"
        assert auth_data["subject"] == device_id
        token = auth_data["access_token"]

        # 3. Acquire console token to list devices
        console_resp = await client.post(
            "/api/v1/auth/console-token",
            json={"api_key": settings.CONSOLE_API_KEY}
        )
        assert console_resp.status_code == 200
        console_token = console_resp.json()["access_token"]

        # 4. List devices using console token
        list_resp = await client.get(
            "/api/v1/devices",
            headers={"Authorization": f"Bearer {console_token}"}
        )
        assert list_resp.status_code == 200
        devices = list_resp.json()
        assert any(d["device_id"] == device_id for d in devices)

        # 5. Start and end session using authenticated device token
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        start_resp = await client.post(
            "/api/v1/sessions/start",
            json={"session_id": session_id, "device_id": device_id},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert start_resp.status_code == 200
        sess_data = start_resp.json()
        assert sess_data["session_id"] == session_id
        assert sess_data["status"] == "ACTIVE"

        end_resp = await client.post(
            f"/api/v1/sessions/{session_id}/end",
            json={"summary": {"test": True}},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert end_resp.status_code == 200
        assert end_resp.json()["status"] == "COMPLETED"
