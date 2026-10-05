from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import SessionRepository, DeviceRepository

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionStartRequest(BaseModel):
    session_id: str
    device_id: str


class SessionEndRequest(BaseModel):
    summary: Optional[Dict[str, Any]] = None


class SessionResponse(BaseModel):
    session_id: str
    device_id: str
    status: str
    started_at: str
    ended_at: Optional[str]


@router.post("/start", response_model=SessionResponse)
async def start_session(req: SessionStartRequest, db: AsyncSession = Depends(get_db)):
    dev_repo = DeviceRepository(db)
    device = await dev_repo.get_by_id(req.device_id)
    if not device:
        # Auto-register device if not existing
        await dev_repo.register_or_update(device_id=req.device_id, name=f"Device {req.device_id[:8]}")

    sess_repo = SessionRepository(db)
    session = await sess_repo.start_session(session_id=req.session_id, device_id=req.device_id)
    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )


@router.post("/{session_id}/end", response_model=SessionResponse)
async def end_session(session_id: str, req: SessionEndRequest, db: AsyncSession = Depends(get_db)):
    sess_repo = SessionRepository(db)
    session = await sess_repo.end_session(session_id=session_id, summary=req.summary)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return SessionResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        status=session.status,
        started_at=session.started_at.isoformat(),
        ended_at=session.ended_at.isoformat() if session.ended_at else None
    )
