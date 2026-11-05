import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean, DateTime, ForeignKey, JSON, Text, Index
)
from sqlalchemy.orm import relationship
from app.db.session import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeviceModel(Base):
    __tablename__ = "devices"

    device_id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    model = Column(String(128), nullable=True)
    os_version = Column(String(64), nullable=True)
    app_version = Column(String(64), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, REVOKED, SUSPENDED
    api_key_hash = Column(String(256), nullable=True)             # bcrypt hashed device credential
    key_rotation_count = Column(Integer, default=0, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    sessions = relationship("SessionModel", back_populates="device", cascade="all, delete-orphan")
    health_records = relationship("DeviceHealthModel", back_populates="device", cascade="all, delete-orphan")


class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True, index=True)
    device_id = Column(String(64), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="ACTIVE", nullable=False)  # ACTIVE, COMPLETED, ABORTED
    summary = Column(JSON, nullable=True)

    device = relationship("DeviceModel", back_populates="sessions")
    snapshots = relationship("SensorSnapshotModel", back_populates="session", cascade="all, delete-orphan")
    expert_runs = relationship("ExpertRunModel", back_populates="session", cascade="all, delete-orphan")
    events = relationship("EventModel", back_populates="session", cascade="all, delete-orphan")
    locations = relationship("LocationModel", back_populates="session", cascade="all, delete-orphan")


class SensorSnapshotModel(Base):
    __tablename__ = "sensor_snapshots"

    snapshot_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(String(64), nullable=False, index=True)
    timestamp_ns = Column(BigInteger, nullable=False, index=True)
    values = Column(JSON, nullable=False)  # list of float values
    accuracy = Column(String(32), default="HIGH", nullable=False)
    orientation = Column(String(32), default="UNKNOWN", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("SessionModel", back_populates="snapshots")


class ExpertRunModel(Base):
    __tablename__ = "expert_runs"

    run_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    expert_id = Column(String(64), nullable=False, index=True)
    capability = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False)
    prediction = Column(String(256), nullable=True)
    confidence = Column(Float, default=0.0, nullable=False)
    latency_ms = Column(Float, nullable=False)
    timestamp_ns = Column(BigInteger, nullable=False)
    provenance = Column(JSON, nullable=True)
    limitations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("SessionModel", back_populates="expert_runs")
    evidences = relationship("EvidenceModel", back_populates="expert_run", cascade="all, delete-orphan")


class EvidenceModel(Base):
    __tablename__ = "evidence_items"

    evidence_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String(64), ForeignKey("expert_runs.run_id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    timestamp_ns = Column(BigInteger, nullable=False)
    source_sensor = Column(String(64), nullable=False)
    attributes = Column(JSON, nullable=False)
    weight = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    expert_run = relationship("ExpertRunModel", back_populates="evidences")


class EventModel(Base):
    __tablename__ = "events"

    event_id = Column(String(64), primary_key=True, index=True)
    session_id = Column(String(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    timestamp_ns = Column(BigInteger, nullable=False, index=True)
    confidence_breakdown = Column(JSON, nullable=False)
    contributing_evidence_ids = Column(JSON, nullable=False)
    explanation = Column(Text, nullable=False)
    haptic_pattern = Column(String(64), default="PULSE_ALERT", nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_dismissed = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("SessionModel", back_populates="events")


class LocationModel(Base):
    __tablename__ = "locations"

    location_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)
    accuracy_meters = Column(Float, nullable=False)
    speed_mps = Column(Float, nullable=True)
    bearing_degrees = Column(Float, nullable=True)
    timestamp_ns = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    session = relationship("SessionModel", back_populates="locations")


class DeviceHealthModel(Base):
    __tablename__ = "device_health"

    health_id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    battery_level = Column(Float, nullable=False)
    battery_temp_c = Column(Float, nullable=False)
    thermal_state = Column(String(32), nullable=False)
    network_type = Column(String(32), nullable=False)
    active_sensors = Column(JSON, nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    device = relationship("DeviceModel", back_populates="health_records")
