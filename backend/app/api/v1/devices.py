from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import DeviceRepository, TelemetryRepository
from app.db.models import DeviceModel
from app.schemas.transport import DeviceStatusPayload
from app.api.deps import get_current_device, get_current_console, verify_provisioning_key
from app.core.security import generate_secure_device_secret

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceProvisionRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, description="Unique hardware identifier")
    name: str = Field(..., min_length=1, max_length=128)
    model: Optional[str] = Field(None, max_length=128)
    os_version: Optional[str] = Field(None, max_length=64)
    app_version: Optional[str] = Field(None, max_length=64)
    device_secret: Optional[str] = Field(None, min_length=16, description="Optional custom secret; generated if omitted")


class DeviceProvisionResponse(BaseModel):
    device_id: str
    name: str
    device_secret: str
    secret: Optional[str] = None
    status: str
    is_active: bool
    created_at: str


class DeviceRotateKeyRequest(BaseModel):
    current_secret: str
    new_secret: Optional[str] = None


class DeviceRotateKeyResponse(BaseModel):
    device_id: str
    new_secret: str
    key_rotation_count: int
    status: str


class DeviceResponse(BaseModel):
    device_id: str
    name: str
    model: Optional[str]
    os_version: Optional[str]
    app_version: Optional[str]
    status: str
    is_active: bool
    key_rotation_count: int
    last_seen_at: str


@router.post("/register", response_model=DeviceProvisionResponse)
@router.post("/provision", response_model=DeviceProvisionResponse)
async def provision_device(
    req: DeviceProvisionRequest,
    _prov_key: str = Depends(verify_provisioning_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Securely provision a new device with per-device credentials.
    Requires X-Provisioning-Key header. Returns device_secret once.
    """
    secret = req.device_secret or generate_secure_device_secret()
    repo = DeviceRepository(db)
    device = await repo.provision_device(
        device_id=req.device_id,
        name=req.name,
        secret=secret,
        model=req.model,
        os_version=req.os_version,
        app_version=req.app_version
    )
    return DeviceProvisionResponse(
        device_id=device.device_id,
        name=device.name,
        device_secret=secret,
        secret=secret,
        status=device.status,
        is_active=device.is_active,
        created_at=device.created_at.isoformat()
    )


@router.post("/{device_id}/rotate-key", response_model=DeviceRotateKeyResponse)
async def rotate_device_key(
    device_id: str,
    req: DeviceRotateKeyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Rotate a device's cryptographic credentials.
    Requires proving ownership via current_secret.
    """
    repo = DeviceRepository(db)
    new_sec = req.new_secret or generate_secure_device_secret()
    device = await repo.rotate_key(
        device_id=device_id,
        old_secret=req.current_secret,
        new_secret=new_sec
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current credentials invalid or device is revoked"
        )
    return DeviceRotateKeyResponse(
        device_id=device.device_id,
        new_secret=new_sec,
        key_rotation_count=device.key_rotation_count,
        status=device.status
    )


@router.post("/{device_id}/revoke")
async def revoke_device(
    device_id: str,
    _prov_key: str = Depends(verify_provisioning_key),
    db: AsyncSession = Depends(get_db)
):
    """
    Immediately revoke a device and deactivate its telemetry capability.
    Requires X-Provisioning-Key header.
    """
    repo = DeviceRepository(db)
    device = await repo.revoke_device(device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return {"status": "revoked", "device_id": device_id, "revoked_at": device.revoked_at.isoformat()}


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    _console: dict = Depends(get_current_console),
    db: AsyncSession = Depends(get_db)
):
    """List registered devices. Requires console operator scope."""
    repo = DeviceRepository(db)
    devices = await repo.list_devices()
    return [
        DeviceResponse(
            device_id=d.device_id,
            name=d.name,
            model=d.model,
            os_version=d.os_version,
            app_version=d.app_version,
            status=d.status,
            is_active=d.is_active,
            key_rotation_count=d.key_rotation_count,
            last_seen_at=d.last_seen_at.isoformat()
        )
        for d in devices
    ]


@router.post("/{device_id}/status")
async def report_device_status(
    device_id: str,
    status_payload: DeviceStatusPayload,
    current_device: DeviceModel = Depends(get_current_device),
    db: AsyncSession = Depends(get_db)
):
    """Report hardware state. Device identity is strictly bound to token."""
    if current_device.device_id != device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Token subject '{current_device.device_id}' does not match route device_id '{device_id}'"
        )

    telemetry_repo = TelemetryRepository(db)
    await telemetry_repo.save_device_health(device_id, status_payload)
    return {"status": "success", "device_id": device_id}
