from datetime import timedelta
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenRequest(BaseModel):
    device_id: str
    api_key: str = "streetsense_default_device_key"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


@router.post("/token", response_model=TokenResponse)
async def acquire_token(req: TokenRequest) -> TokenResponse:
    if not req.device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="device_id is required"
        )
    access_token = create_access_token(
        data={"sub": req.device_id, "type": "device"},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
