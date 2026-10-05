from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import (
    TelemetryRepository, ExpertRunRepository, EventRepository, SessionRepository
)
from app.schemas.transport import TelemetryIngressPayload

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/batch/{session_id}", status_code=status.HTTP_200_OK)
async def ingest_batch_telemetry(
    session_id: str,
    payload: TelemetryIngressPayload,
    db: AsyncSession = Depends(get_db)
):
    # Ensure session exists
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(session_id)
    if not session:
        # Default device if not yet created
        await sess_repo.start_session(session_id, device_id="batch_sync_device")

    telemetry_repo = TelemetryRepository(db)
    if payload.snapshots:
        await telemetry_repo.save_sensor_snapshots(session_id, payload.snapshots)

    if payload.location:
        await telemetry_repo.save_location(session_id, payload.location)

    if payload.device_status and session:
        await telemetry_repo.save_device_health(session.device_id, payload.device_status)

    expert_repo = ExpertRunRepository(db)
    for res in payload.expert_results:
        await expert_repo.save_expert_run(session_id, res)

    if payload.evidences:
        await expert_repo.save_evidence_items(session_id, None, payload.evidences)

    event_repo = EventRepository(db)
    for evt in payload.events:
        await event_repo.save_event(evt)

    return {
        "status": "synced",
        "snapshots_count": len(payload.snapshots),
        "expert_runs_count": len(payload.expert_results),
        "events_count": len(payload.events),
    }
