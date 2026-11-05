import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, desc
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
from app.core.security import hash_device_secret, verify_device_secret


class DeviceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, device_id: str) -> Optional[DeviceModel]:
        stmt = select(DeviceModel).where(DeviceModel.device_id == device_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def provision_device(
        self,
        device_id: str,
        name: str,
        secret: str,
        model: Optional[str] = None,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None
    ) -> DeviceModel:
        """Register or re-provision a device with a cryptographic secret verifier."""
        device = await self.get_by_id(device_id)
        now = datetime.now(timezone.utc)
        api_key_hash = hash_device_secret(secret)

        if device is None:
            device = DeviceModel(
                device_id=device_id,
                name=name,
                model=model,
                os_version=os_version,
                app_version=app_version,
                is_active=True,
                status="ACTIVE",
                api_key_hash=api_key_hash,
                key_rotation_count=0,
                created_at=now,
                last_seen_at=now
            )
            self.db.add(device)
        else:
            device.name = name
            device.model = model or device.model
            device.os_version = os_version or device.os_version
            device.app_version = app_version or device.app_version
            device.is_active = True
            device.status = "ACTIVE"
            device.api_key_hash = api_key_hash
            device.revoked_at = None
            device.last_seen_at = now

        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def verify_credentials(self, device_id: str, secret: str) -> Optional[DeviceModel]:
        """Authenticate a device against its stored verifier. Validates status is ACTIVE."""
        device = await self.get_by_id(device_id)
        if not device:
            return None

        if not device.is_active or device.status != "ACTIVE":
            return None

        if not verify_device_secret(secret, device.api_key_hash):
            return None

        device.last_seen_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def rotate_key(self, device_id: str, old_secret: str, new_secret: str) -> Optional[DeviceModel]:
        """Rotate device secret after verifying existing credentials."""
        device = await self.verify_credentials(device_id, old_secret)
        if not device:
            return None

        device.api_key_hash = hash_device_secret(new_secret)
        device.key_rotation_count += 1
        device.last_seen_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(device)
        return device

    async def revoke_device(self, device_id: str) -> Optional[DeviceModel]:
        """Immediately revoke a device and deactivate all associated access."""
        device = await self.get_by_id(device_id)
        if not device:
            return None

        device.is_active = False
        device.status = "REVOKED"
        device.revoked_at = datetime.now(timezone.utc)
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
        """Start a session strictly for an active, registered device."""
        dev_stmt = select(DeviceModel).where(DeviceModel.device_id == device_id)
        dev_res = await self.db.execute(dev_stmt)
        device = dev_res.scalar_one_or_none()
        if not device or not device.is_active or device.status != "ACTIVE":
            raise ValueError(f"Cannot start session for unprovisioned or non-active device '{device_id}'")

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
            if session.device_id != device_id:
                raise ValueError(f"Session '{session_id}' belongs to another device '{session.device_id}'")
            session.started_at = now
            session.ended_at = None
            session.status = "ACTIVE"
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def verify_session_owner(self, session_id: str, device_id: str) -> bool:
        """Cryptographically check if a session belongs to the requesting device."""
        session = await self.get_by_id(session_id)
        if not session:
            return False
        return session.device_id == device_id

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

    async def purge_expired_records(self, retention_days: int) -> int:
        """Enforce privacy retention policy by purging raw location and sensor snapshots older than retention days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        stmt1 = delete(SensorSnapshotModel).where(SensorSnapshotModel.created_at < cutoff)
        res1 = await self.db.execute(stmt1)
        stmt2 = delete(LocationModel).where(LocationModel.created_at < cutoff)
        res2 = await self.db.execute(stmt2)
        await self.db.commit()
        return (res1.rowcount or 0) + (res2.rowcount or 0)


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
