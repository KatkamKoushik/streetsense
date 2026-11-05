from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import SessionRepository
from app.db.models import DeviceModel
from app.api.deps import get_current_device, get_authenticated_principal

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionStartRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)
    device_id: Optional[str] = Field(None, max_length=64, description="Optional; must match token if provided")


class SessionEndRequest(BaseModel):
    summary: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    session_id: str
    device_id: str
    status: str
    started_at: str
    ended_at: Optional[str]


@router.post("/start", response_model=SessionResponse)
async def start_session(
    req: SessionStartRequest,
    current_device: DeviceModel = Depends(get_current_device),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a telemetry session. Bound strictly to the authenticated device.
    Rejects mismatched device_id or unknown devices.
    """
    if req.device_id and req.device_id != current_device.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Authenticated device '{current_device.device_id}' cannot start a session for '{req.device_id}'"
        )

    sess_repo = SessionRepository(db)
    try:
        session = await sess_repo.start_session(session_id=req.session_id, device_id=current_device.device_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    req: SessionEndRequest,
    principal: Dict[str, Any] = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """End a telemetry session. Verified against device identity or console operator."""
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if principal["type"] == "device" and session.device_id != principal["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device '{principal['sub']}' cannot end session belonging to '{session.device_id}'"
        )

    session = await sess_repo.end_session(session_id=session_id, summary=req.summary)
    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    principal: Dict[str, Any] = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """Fetch session details. Devices may only view their own sessions; console can view all."""
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if principal["type"] == "device" and session.device_id != principal["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Cannot view another device's session"
        )

    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )
