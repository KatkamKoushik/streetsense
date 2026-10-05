from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import DeviceRepository, TelemetryRepository
from app.schemas.transport import DeviceStatusPayload

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    model: Optional[str] = None
    os_version: Optional[str] = None
    app_version: Optional[str] = None


class DeviceResponse(BaseModel):
    device_id: str
    name: str
    model: Optional[str]
    os_version: Optional[str]
    app_version: Optional[str]
    is_active: bool
    last_seen_at: str


@router.post("/register", response_model=DeviceResponse)
async def register_device(req: DeviceRegisterRequest, db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    device = await repo.register_or_update(
        device_id=req.device_id,
        name=req.name,
        model=req.model,
        os_version=req.os_version,
        app_version=req.app_version
    )
    return DeviceResponse(
        device_id=device.device_id,
        name=device.name,
        model=device.model,
        os_version=device.os_version,
        app_version=device.app_version,
        is_active=device.is_active,
        last_seen_at=device.last_seen_at.isoformat()
    )


@router.get("", response_model=List[DeviceResponse])
async def list_devices(db: AsyncSession = Depends(get_db)):
    repo = DeviceRepository(db)
    devices = await repo.list_devices()
    return [
        DeviceResponse(
            device_id=d.device_id,
            name=d.name,
            model=d.model,
            os_version=d.os_version,
            app_version=d.app_version,
            is_active=d.is_active,
            last_seen_at=d.last_seen_at.isoformat()
        )
        for d in devices
    ]


@router.post("/{device_id}/status")
async def report_device_status(
    device_id: str,
    status_payload: DeviceStatusPayload,
    db: AsyncSession = Depends(get_db)
):
    repo = DeviceRepository(db)
    device = await repo.get_by_id(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    telemetry_repo = TelemetryRepository(db)
    await telemetry_repo.save_device_health(device_id, status_payload)
    return {"status": "success", "device_id": device_id}
