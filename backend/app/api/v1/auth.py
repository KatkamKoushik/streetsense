from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import create_device_token, create_console_token
from app.db.session import get_db
from app.db.repositories import DeviceRepository

router = APIRouter(prefix="/auth", tags=["auth"])


class DeviceTokenRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64, description="Provisioned device ID")
    device_secret: Optional[str] = Field(None, min_length=8, description="Cryptographic per-device secret")
    api_key: Optional[str] = Field(None, min_length=8, description="Alias for device_secret")

    def get_secret(self) -> str:
        s = self.device_secret or self.api_key
        if not s:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid device credentials: missing device_secret or api_key",
                headers={"WWW-Authenticate": "Bearer error=\"invalid_client\""}
            )
        return s


class ConsoleTokenRequest(BaseModel):
    api_key: str = Field(..., min_length=8, description="Web console operator API key")
    client_id: Optional[str] = Field("web_console_operator", max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    subject: str


@router.post("/token", response_model=TokenResponse)
async def acquire_device_token(
    req: DeviceTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Acquire a device telemetry token.
    Cryptographically validates the device secret against the stored verifier.
    Rejects unknown, revoked, or suspended devices.
    """
    dev_repo = DeviceRepository(db)
    secret = req.get_secret()
    device = await dev_repo.verify_credentials(device_id=req.device_id, secret=secret)

    if not device:
        # Check if device exists to provide accurate security rejection
        existing = await dev_repo.get_by_id(req.device_id)
        if existing and (not existing.is_active or existing.status != "ACTIVE"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Device '{req.device_id}' access has been revoked or suspended"
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device credentials",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_client\""}
        )

    access_token = create_device_token(
        device_id=device.device_id,
        scopes=["device:telemetry"],
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        subject=device.device_id
    )


@router.post("/console-token", response_model=TokenResponse)
async def acquire_console_token(
    req: Optional[ConsoleTokenRequest] = None,
    x_console_key: Optional[str] = Header(None, alias="X-Console-Key")
) -> TokenResponse:
    """
    Acquire an observation console token.
    Validates console API key against the configured secret and issues an observer JWT.
    Supports either JSON body {api_key: ...} or X-Console-Key header.
    """
    api_key = (req.api_key if req else None) or x_console_key
    if not api_key or api_key != settings.CONSOLE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid console API key",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_client\""}
        )

    client_id = (req.client_id if req else None) or "web_console_operator"
    access_token = create_console_token(
        client_id=client_id,
        scopes=["console:observe"],
        expires_delta=timedelta(minutes=settings.CONSOLE_TOKEN_EXPIRE_MINUTES)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.CONSOLE_TOKEN_EXPIRE_MINUTES,
        subject=client_id
    )
