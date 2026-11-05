from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import EventRepository, SessionRepository
from app.db.models import DeviceModel
from app.schemas.events import DetectedEvent
from app.api.deps import get_current_device, get_current_console, get_authenticated_principal

router = APIRouter(prefix="/events", tags=["events"])


class EventResponse(BaseModel):
    event_id: str
    session_id: str
    category: str
    severity: str
    timestamp_ns: int
    confidence_breakdown: dict
    contributing_evidence_ids: list
    explanation: str
    haptic_pattern: str
    latitude: Optional[float]
    longitude: Optional[float]
    is_dismissed: bool


@router.post("", response_model=EventResponse)
async def create_event(
    event: DetectedEvent,
    current_device: DeviceModel = Depends(get_current_device),
    db: AsyncSession = Depends(get_db)
):
    """Publish a detected hazard event. Bound strictly to device session."""
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(event.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{event.session_id}' not found"
        )

    if session.device_id != current_device.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Device '{current_device.device_id}' cannot publish events to session '{session.session_id}'"
        )

    repo = EventRepository(db)
    saved = await repo.save_event(event)
    return EventResponse(
        event_id=saved.event_id,
        session_id=saved.session_id,
        category=saved.category,
        severity=saved.severity,
        timestamp_ns=saved.timestamp_ns,
        confidence_breakdown=saved.confidence_breakdown,
        contributing_evidence_ids=saved.contributing_evidence_ids,
        explanation=saved.explanation,
        haptic_pattern=saved.haptic_pattern,
        latitude=saved.latitude,
        longitude=saved.longitude,
        is_dismissed=saved.is_dismissed
    )


@router.get("", response_model=List[EventResponse])
async def list_events(
    session_id: Optional[str] = None,
    limit: int = 50,
    principal: Dict[str, Any] = Depends(get_authenticated_principal),
    db: AsyncSession = Depends(get_db)
):
    """List recent events. Console operators see all; devices only see their own sessions."""
    if principal["type"] == "device" and session_id:
        sess_repo = SessionRepository(db)
        session = await sess_repo.get_by_id(session_id)
        if session and session.device_id != principal["sub"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Cannot list events for another device's session"
            )

    repo = EventRepository(db)
    events = await repo.list_recent_events(session_id=session_id, limit=limit)
    return [
        EventResponse(
            event_id=e.event_id,
            session_id=e.session_id,
            category=e.category,
            severity=e.severity,
            timestamp_ns=e.timestamp_ns,
            confidence_breakdown=e.confidence_breakdown,
            contributing_evidence_ids=e.contributing_evidence_ids,
            explanation=e.explanation,
            haptic_pattern=e.haptic_pattern,
            latitude=e.latitude,
            longitude=e.longitude,
            is_dismissed=e.is_dismissed
        )
        for e in events
    ]


@router.post("/{event_id}/dismiss", response_model=EventResponse)
async def dismiss_event(
    event_id: str,
    _console: dict = Depends(get_current_console),
    db: AsyncSession = Depends(get_db)
):
    """Dismiss an event alert. Restricted to console operators."""
    repo = EventRepository(db)
    event = await repo.dismiss_event(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return EventResponse(
        event_id=event.event_id,
        session_id=event.session_id,
        category=event.category,
        severity=event.severity,
        timestamp_ns=event.timestamp_ns,
        confidence_breakdown=event.confidence_breakdown,
        contributing_evidence_ids=event.contributing_evidence_ids,
        explanation=event.explanation,
        haptic_pattern=event.haptic_pattern,
        latitude=event.latitude,
        longitude=event.longitude,
        is_dismissed=event.is_dismissed
    )
