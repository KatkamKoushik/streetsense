from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import EventRepository
from app.schemas.events import DetectedEvent, EventCategory, EventSeverity, ConfidenceBreakdown

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
async def create_event(event: DetectedEvent, db: AsyncSession = Depends(get_db)):
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
    db: AsyncSession = Depends(get_db)
):
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
async def dismiss_event(event_id: str, db: AsyncSession = Depends(get_db)):
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
