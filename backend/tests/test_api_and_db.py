import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.init_db import init_db


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


@pytest.mark.asyncio
async def test_auth_token_generation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"device_id": "test_device_001", "api_key": "test_key"}
        resp = await client.post("/api/v1/auth/token", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_device_registration_and_listing():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dev_payload = {
            "device_id": "pixel_8_pro_test",
            "name": "Pixel 8 Pro Tester",
            "model": "Pixel 8 Pro",
            "os_version": "Android 14",
            "app_version": "1.0.0"
        }
        resp = await client.post("/api/v1/devices/register", json=dev_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["device_id"] == "pixel_8_pro_test"

        resp_list = await client.get("/api/v1/devices")
        assert resp_list.status_code == 200
        devices = resp_list.json()
        assert any(d["device_id"] == "pixel_8_pro_test" for d in devices)


@pytest.mark.asyncio
async def test_session_lifecycle():
    import uuid
    test_session_id = f"sess_{uuid.uuid4().hex[:8]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start session
        start_payload = {
            "session_id": test_session_id,
            "device_id": "pixel_8_pro_test"
        }
        resp = await client.post("/api/v1/sessions/start", json=start_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == test_session_id
        assert data["status"] == "ACTIVE"

        # End session
        end_payload = {"summary": {"total_events": 0}}
        resp_end = await client.post(f"/api/v1/sessions/{test_session_id}/end", json=end_payload)
        assert resp_end.status_code == 200
        data_end = resp_end.json()
        assert data_end["status"] == "COMPLETED"
        assert data_end["ended_at"] is not None
