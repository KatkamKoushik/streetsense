from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import decode_and_verify_token
from app.db.session import get_db
from app.db.models import DeviceModel
from app.db.repositories import DeviceRepository

security_scheme = HTTPBearer(auto_error=False)


async def get_current_device(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> DeviceModel:
    """
    Authenticate a device via signed JWT bearer token.
    Validates token issuer, audience ('streetsense:telemetry'), scope, expiry,
    and confirms device is registered and status == 'ACTIVE'.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Device authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    claims = decode_and_verify_token(
        token=credentials.credentials,
        expected_audience=settings.JWT_AUDIENCE_DEVICE,
        required_scope="device:telemetry"
    )

    device_id = claims.get("device_id") or claims.get("sub")
    if not device_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject does not identify a device",
            headers={"WWW-Authenticate": "Bearer"}
        )

    dev_repo = DeviceRepository(db)
    device = await dev_repo.get_by_id(device_id)

    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Device '{device_id}' is not registered",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"unknown device\""}
        )

    if not device.is_active or device.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device '{device_id}' is revoked or suspended (status: {device.status})",
            headers={"WWW-Authenticate": "Bearer error=\"insufficient_scope\", error_description=\"device revoked\""}
        )

    return device


async def get_current_console(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    Authenticate an operator or web console via signed JWT bearer token.
    Validates token issuer, audience ('streetsense:console'), scope ('console:observe'), and expiry.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Console authorization token required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    claims = decode_and_verify_token(
        token=credentials.credentials,
        expected_audience=settings.JWT_AUDIENCE_CONSOLE,
        required_scope="console:observe"
    )

    return claims


async def get_authenticated_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Accepts either an active device OR an authorized console operator.
    Useful for shared read endpoints like sessions and events.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    # Try console first
    try:
        claims = decode_and_verify_token(
            token=token,
            expected_audience=settings.JWT_AUDIENCE_CONSOLE,
            required_scope="console:observe"
        )
        return {"type": "console", "sub": claims.get("sub"), "claims": claims}
    except HTTPException:
        pass

    # Try device
    try:
        claims = decode_and_verify_token(
            token=token,
            expected_audience=settings.JWT_AUDIENCE_DEVICE,
            required_scope="device:telemetry"
        )
        device_id = claims.get("device_id") or claims.get("sub")
        dev_repo = DeviceRepository(db)
        device = await dev_repo.get_by_id(device_id)
        if not device or not device.is_active or device.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Device '{device_id}' is revoked or not active"
            )
        return {"type": "device", "sub": device_id, "device": device, "claims": claims}
    except HTTPException as e:
        raise e


def verify_provisioning_key(
    x_provisioning_key: Optional[str] = Header(None, alias="X-Provisioning-Key")
) -> str:
    """Enforce secret key authentication for device enrollment and provisioning."""
    if not x_provisioning_key or x_provisioning_key != settings.DEVICE_PROVISIONING_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Provisioning-Key"
        )
    return x_provisioning_key

