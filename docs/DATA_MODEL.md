# StreetSense — Data Model & Storage Specification

## 1. Relational Database Schema (PostgreSQL + PostGIS)

The backend data model models all entities involved in mobile environmental sensing, expert execution telemetry, evidence traces, and hazard lifecycle.

```mermaid
erDiagram
    USERS ||--o{ DEVICES : owns
    DEVICES ||--o{ SESSIONS : records
    SESSIONS ||--o{ SENSOR_SNAPSHOTS : contains
    SESSIONS ||--o{ FRAMES : captures
    SESSIONS ||--o{ EXPERT_RUNS : executes
    EXPERT_RUNS ||--o{ EVIDENCE : generates
    SESSIONS ||--o{ EVENTS : detects
    EVENTS ||--o{ ALERTS : triggers
    EVENTS ||--o{ EVENT_EVIDENCE : references
    EVIDENCE ||--o{ EVENT_EVIDENCE : contributes_to
    SESSIONS ||--o{ LOCATIONS : tracks
    DEVICES ||--o{ DEVICE_HEALTH : reports
    SESSIONS ||--o{ SYSTEM_LOGS : emits

    USERS {
        uuid id PK
        varchar email UK
        varchar hashed_password
        varchar full_name
        varchar role
        timestamptz created_at
    }

    DEVICES {
        uuid id PK
        uuid user_id FK
        varchar device_id UK
        varchar model
        varchar manufacturer
        varchar os_version
        varchar app_version
        jsonb hardware_capabilities
        timestamptz registered_at
        timestamptz last_seen_at
    }

    SESSIONS {
        uuid id PK
        uuid device_id FK
        varchar session_token UK
        timestamptz started_at
        timestamptz ended_at
        varchar status
        jsonb metadata
    }

    SENSOR_SNAPSHOTS {
        uuid id PK
        uuid session_id FK
        timestamptz timestamp
        varchar sensor_type
        jsonb values
        int accuracy
        jsonb orientation
    }

    FRAMES {
        uuid id PK
        uuid session_id FK
        timestamptz timestamp
        int width
        int height
        float quality_score
        float blur_index
        float lux
        varchar storage_uri
    }

    EXPERT_RUNS {
        uuid id PK
        uuid session_id FK
        varchar expert_id
        varchar capability
        varchar status
        float confidence
        bigint latency_ms
        timestamptz started_at
        timestamptz completed_at
        jsonb provenance
    }

    EVIDENCE {
        uuid id PK
        uuid expert_run_id FK
        varchar evidence_type
        float confidence
        float quality_score
        jsonb payload
        timestamptz created_at
    }

    EVENTS {
        uuid id PK
        uuid session_id FK
        varchar event_type
        varchar severity
        float confidence
        geometry coordinates
        timestamptz detected_at
        text explanation
        jsonb confidence_breakdown
    }

    ALERTS {
        uuid id PK
        uuid event_id FK
        varchar alert_tier
        boolean haptic_triggered
        boolean voice_triggered
        varchar voice_script
        timestamptz triggered_at
        timestamptz dismissed_at
        varchar dismissal_reason
    }

    EVENT_EVIDENCE {
        uuid event_id PK, FK
        uuid evidence_id PK, FK
        float weight
    }

    LOCATIONS {
        uuid id PK
        uuid session_id FK
        timestamptz timestamp
        geometry coordinate
        float altitude
        float accuracy
        float speed
        float bearing
    }

    DEVICE_HEALTH {
        uuid id PK
        uuid device_id FK
        timestamptz timestamp
        float battery_pct
        float temperature_c
        boolean is_charging
        varchar thermal_status
        bigint memory_free_bytes
    }

    SYSTEM_LOGS {
        uuid id PK
        uuid session_id FK
        timestamptz timestamp
        varchar level
        varchar component
        varchar correlation_id
        text message
        jsonb context
    }
```

---

## 2. Table Specifications & PostGIS Columns

### `locations` & `events` PostGIS Integration
Geospatial fields use standard WGS84 coordinates (`SRID=4326`):
- `locations.coordinate`: `GEOMETRY(Point, 4326)`
- `events.coordinates`: `GEOMETRY(Point, 4326)`

Spatial Indexing:
```sql
CREATE INDEX idx_locations_geom ON locations USING GIST(coordinate);
CREATE INDEX idx_events_geom ON events USING GIST(coordinates);
CREATE INDEX idx_events_detected_at ON events(detected_at DESC);
CREATE INDEX idx_sensor_snapshots_session_time ON sensor_snapshots(session_id, timestamp DESC);
CREATE INDEX idx_expert_runs_session ON expert_runs(session_id, completed_at DESC);
```

---

## 3. Data Retention & Pruning Policies

To prevent unchecked disk growth and maintain high query performance:
1. **Raw Frames**: Never store raw uncompressed frames on disk indefinitely. High-resolution frames are analyzed in-memory at the edge. Selected keyframes with verified hazard evidence are stored compressed with a **7-day retention policy**.
2. **High-Frequency Sensor Snapshots (50 Hz IMU)**: Aggregated into 1-second statistical summaries (min, max, mean, variance) after **48 hours**. Raw high-frequency ticks older than 48 hours are automatically pruned.
3. **Events, Evidence, and Alerts**: Maintained permanently for auditability, incident reconstruction, and model evaluation.

---

## 4. Mobile Edge SQLite / Room Database Schema

On the Android client, an offline-first SQLite database preserves operational state during connectivity blackouts:

- `local_sessions`: Current active session ID, start time, device sync status.
- `local_events`: Persists generated events before sync confirmation:
  - `event_id` (UUID PK), `timestamp`, `event_type`, `severity`, `confidence`, `payload_json`, `synced_to_backend` (Boolean), `retry_count` (Int).
- `local_evidence`: Cache of recent evidence items for temporal window calculations.
- `local_sensor_buffer`: Sliding window of sensor snapshots used by `TemporalChangeExpert` and `MotionExpert`.
- `sync_queue`: Ordered FIFO queue of outgoing messages with exponential backoff metadata.
