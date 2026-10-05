from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    DeviceModel, SessionModel, SensorSnapshotModel, ExpertRunModel,
    EvidenceModel, EventModel, LocationModel, DeviceHealthModel
)
from app.schemas.sensors import SensorSnapshot, LocationSnapshot
from app.schemas.experts import ExpertResult
from app.schemas.evidence import EvidenceItem
from app.schemas.events import DetectedEvent
from app.schemas.transport import DeviceStatusPayload


class DeviceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, device_id: str) -> Optional[DeviceModel]:
        stmt = select(DeviceModel).where(DeviceModel.device_id == device_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def register_or_update(
        self, device_id: str, name: str, model: Optional[str] = None,
        os_version: Optional[str] = None, app_version: Optional[str] = None
    ) -> DeviceModel:
        device = await self.get_by_id(device_id)
        now = datetime.now(timezone.utc)
        if device is None:
            device = DeviceModel(
                device_id=device_id,
                name=name,
                model=model,
                os_version=os_version,
                app_version=app_version,
                is_active=True,
                last_seen_at=now
            )
            self.db.add(device)
        else:
            device.name = name
            device.model = model or device.model
            device.os_version = os_version or device.os_version
            device.app_version = app_version or device.app_version
            device.last_seen_at = now
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def list_devices(self) -> List[DeviceModel]:
        stmt = select(DeviceModel).order_by(desc(DeviceModel.last_seen_at))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, session_id: str) -> Optional[SessionModel]:
        stmt = select(SessionModel).where(SessionModel.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def start_session(self, session_id: str, device_id: str) -> SessionModel:
        session = await self.get_by_id(session_id)
        now = datetime.now(timezone.utc)
        if session is None:
            session = SessionModel(
                session_id=session_id,
                device_id=device_id,
                started_at=now,
                status="ACTIVE"
            )
            self.db.add(session)
        else:
            session.device_id = device_id
            session.started_at = now
            session.ended_at = None
            session.status = "ACTIVE"
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def end_session(self, session_id: str, summary: Optional[Dict[str, Any]] = None) -> Optional[SessionModel]:
        session = await self.get_by_id(session_id)
        if session:
            session.ended_at = datetime.now(timezone.utc)
            session.status = "COMPLETED"
            session.summary = summary
            await self.db.commit()
            await self.db.refresh(session)
        return session


class TelemetryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_sensor_snapshots(self, session_id: str, snapshots: List[SensorSnapshot]) -> None:
        models = [
            SensorSnapshotModel(
                session_id=session_id,
                sensor_type=s.sensor_type.value,
                timestamp_ns=s.timestamp_ns,
                values=s.values,
                accuracy=s.accuracy.value,
                orientation=s.orientation.value,
            )
            for s in snapshots
        ]
        self.db.add_all(models)
        await self.db.commit()

    async def save_location(self, session_id: str, loc: LocationSnapshot) -> LocationModel:
        model = LocationModel(
            session_id=session_id,
            latitude=loc.latitude,
            longitude=loc.longitude,
            altitude=loc.altitude,
            accuracy_meters=loc.accuracy_meters,
            speed_mps=loc.speed_mps,
            bearing_degrees=loc.bearing_degrees,
            timestamp_ns=loc.timestamp_ns,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def save_device_health(self, device_id: str, health: DeviceStatusPayload) -> DeviceHealthModel:
        model = DeviceHealthModel(
            device_id=device_id,
            battery_level=health.battery_level,
            battery_temp_c=health.battery_temperature_c,
            thermal_state=health.thermal_state,
            network_type=health.network_type,
            active_sensors=health.active_sensors,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model


class ExpertRunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_expert_run(self, session_id: str, result: ExpertResult) -> ExpertRunModel:
        model = ExpertRunModel(
            session_id=session_id,
            expert_id=result.expert_id,
            capability=result.capability.value,
            status=result.status.value,
            prediction=result.prediction,
            confidence=result.confidence,
            latency_ms=result.latency_ms,
            timestamp_ns=result.timestamp_ns,
            provenance=result.provenance.model_dump(),
            limitations=result.limitations,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def save_evidence_items(self, session_id: str, run_id: Optional[str], items: List[EvidenceItem]) -> None:
        models = [
            EvidenceModel(
                evidence_id=item.evidence_id,
                run_id=run_id,
                session_id=session_id,
                evidence_type=item.evidence_type.value,
                confidence=item.confidence,
                timestamp_ns=item.timestamp_ns,
                source_sensor=item.source_sensor,
                attributes=item.attributes,
                weight=item.weight,
            )
            for item in items
        ]
        self.db.add_all(models)
        await self.db.commit()


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_event(self, event: DetectedEvent) -> EventModel:
        model = EventModel(
            event_id=event.event_id,
            session_id=event.session_id,
            category=event.category.value,
            severity=event.severity.value,
            timestamp_ns=event.timestamp_ns,
            confidence_breakdown=event.confidence_breakdown.model_dump(),
            contributing_evidence_ids=event.contributing_evidence_ids,
            explanation=event.explanation,
            haptic_pattern=event.haptic_pattern,
            latitude=event.latitude,
            longitude=event.longitude,
            is_dismissed=event.is_dismissed,
            metadata_json=event.metadata,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return model

    async def list_recent_events(self, session_id: Optional[str] = None, limit: int = 50) -> List[EventModel]:
        stmt = select(EventModel)
        if session_id:
            stmt = stmt.where(EventModel.session_id == session_id)
        stmt = stmt.order_by(desc(EventModel.timestamp_ns)).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def dismiss_event(self, event_id: str) -> Optional[EventModel]:
        stmt = select(EventModel).where(EventModel.event_id == event_id)
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.is_dismissed = True
            await self.db.commit()
            await self.db.refresh(model)
        return model
