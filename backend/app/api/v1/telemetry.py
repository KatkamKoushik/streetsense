import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories import (
    TelemetryRepository, ExpertRunRepository, EventRepository, SessionRepository
)
from app.db.models import DeviceModel
from app.schemas.transport import TelemetryIngressPayload
from app.api.deps import get_current_device
from app.core.config import settings

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/batch/{session_id}", status_code=status.HTTP_200_OK)
async def ingest_batch_telemetry(
    session_id: str,
    payload: TelemetryIngressPayload,
    current_device: DeviceModel = Depends(get_current_device),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest batch telemetry. Bound strictly to the authenticated device and its active session.
    Rejects unauthorized devices or mismatched sessions.
    """
    sess_repo = SessionRepository(db)
    session = await sess_repo.get_by_id(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active session '{session_id}' not found. You must explicitly start a session first."
        )

    if session.device_id != current_device.device_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Session '{session_id}' belongs to device '{session.device_id}', not '{current_device.device_id}'"
        )

    # Validate timestamp skew across snapshots
    now_ns = time.time_ns()
    max_skew_ns = settings.MAX_TIMESTAMP_SKEW_SECONDS * 1_000_000_000
    if payload.snapshots:
        for snap in payload.snapshots:
            if abs(now_ns - snap.timestamp_ns) > max_skew_ns:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sensor snapshot timestamp out of allowable skew window ({settings.MAX_TIMESTAMP_SKEW_SECONDS}s)"
                )

    telemetry_repo = TelemetryRepository(db)
    if payload.snapshots:
        await telemetry_repo.save_sensor_snapshots(session_id, payload.snapshots)

    if payload.location:
        await telemetry_repo.save_location(session_id, payload.location)

    if payload.device_status:
        await telemetry_repo.save_device_health(current_device.device_id, payload.device_status)

    expert_repo = ExpertRunRepository(db)
    for res in payload.expert_results:
        await expert_repo.save_expert_run(session_id, res)

    if payload.evidences:
        await expert_repo.save_evidence_items(session_id, None, payload.evidences)

    event_repo = EventRepository(db)
    for evt in payload.events:
        if evt.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Event session_id '{evt.session_id}' does not match route session_id '{session_id}'"
            )
        await event_repo.save_event(evt)

    return {
        "status": "synced",
        "device_id": current_device.device_id,
        "session_id": session_id,
        "snapshots_count": len(payload.snapshots),
        "expert_runs_count": len(payload.expert_results),
        "events_count": len(payload.events),
    }
