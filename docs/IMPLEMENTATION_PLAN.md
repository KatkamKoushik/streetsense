# StreetSense — Master Implementation Plan & System Architecture

## 1. Executive Summary & Objective

StreetSense is a real-time mobile environmental and activity sensing platform powered by a **Selective Multi-Expert Architecture**. Unlike conventional monolithic computer vision or mobile AI pipelines that execute heavy neural networks indiscriminately on every incoming camera frame, StreetSense utilizes a capability-driven orchestration engine. Cheap deterministic sensors and lightweight heuristics (Level 0 and Level 1) run continuously to establish baseline evidence. Expensive edge vision models, temporal sequence analyzers, and local reasoning engines (Level 2 to Level 4) are invoked only when justified by sensor quality, environmental ambiguity, or potential hazard escalation.

### Strict Engineering Guarantees
- **Zero-Mock Policy**: No simulated sensors, random coordinates, fake detections, or synthetic dashboard metrics. Every module either connects to real hardware/inference/backend services or explicitly yields typed `UNAVAILABLE` / `NOT_IMPLEMENTED` states.
- **Explainable Evidence-First Decisions**: High-level alerts are never generated directly from a single opaque model output. Decisions are synthesized through structured evidence items, multi-factor confidence breakdowns, and deterministic arbitration.
- **Fail-Safe Offline-First Operation**: Immediate life-safety alerts are decided and triggered locally on the mobile edge (haptics and UI). Network transport to the backend is asynchronous, buffered in a local SQLite queue, and synced with idempotency guarantees.

---

## 2. System Architecture & Topology

```
+----------------------------------------------------------------------------------------------------+
|                                    ANDROID MOBILE EDGE CLIENT                                      |
|                                                                                                    |
|  [Hardware Sensors]        [CameraX Stream]        [Fused Location]                                |
|   Accel/Gyro/Mag/Lux        ImageAnalysis           GPS/Bearing/Speed                              |
|           │                       │                         │                                      |
|           ▼                       ▼                         ▼                                      |
|   ┌─────────────────────────────────────────────────────────────────┐                              |
|   │            Sensor Normalizer & Temporal Ring Buffer             │                              |
|   └───────────────────────────────┬─────────────────────────────────┘                              |
|                                   │                                                                |
|                                   ▼                                                                |
|   ┌─────────────────────────────────────────────────────────────────┐                              |
|   │              Selective Multi-Expert Router (L0-L4)              │                              |
|   │  - Level 0: Sensor Quality Check (Jitter/Noise)                 │                              |
|   │  - Level 1: Inexpensive IMU Motion & Ambient Illumination       │                              |
|   │  - Level 2: On-Demand Edge Vision (TFLite/ONNX Mobile)          │                              |
|   │  - Level 3: Temporal Persistence & Spatial Context              │                              |
|   │  - Level 4: Grounded Local Reasoning Explanation                │                              |
|   └───────────────┬───────────────────────────────┬─────────────────┘                              |
|                   │                               │                                                |
|                   ▼                               ▼                                                |
|   ┌───────────────────────────────┐   ┌───────────────────────────────┐                            |
|   │     Evidence Fusion Engine    │   │      Arbitration Engine       │                            |
|   └───────────────┬───────────────┘   └───────────────┬───────────────┘                            |
|                   └───────────────┬───────────────────┘                                            |
|                                   ▼                                                                |
|   ┌─────────────────────────────────────────────────────────────────┐                              |
|   │          Deterministic Final Event Decision & Alerting          │                              |
|   │   - Haptic Engine (Vibrator) & Jetpack Compose HUD              │                              |
|   │   - Room SQLite Offline Persistence & Sync Queue                │                              |
|   └───────────────────────────────┬─────────────────────────────────┘                              |
+-----------------------------------┼----------------------------------------------------------------+
                                    │ WebSocket / TLS (Authenticated WsMessageEnvelope)
                                    ▼
+----------------------------------------------------------------------------------------------------+
|                                    REAL-TIME BACKEND GATEWAY                                       |
|                                                                                                    |
|   ┌─────────────────────────────────────────────────────────────────┐                              |
|   │        FastAPI Ingress Router (/ws/telemetry, /api/v1/*)        │                              |
|   │   - JWT Device Authentication & Session Manager                 │                              |
|   │   - Message Deduplication & Sequence Monotonicity               │                              |
|   └───────────────┬───────────────────────────────┬─────────────────┘                              |
|                   │                               │                                                |
|                   ▼                               ▼                                                |
|   ┌───────────────────────────────┐   ┌───────────────────────────────┐                            |
|   │   Real-Time Broadcast Hub     │   │   Async Storage Engine        │                            |
|   │   PubSub to Office Kit Clients│   │   SQLAlchemy 2.0 Async        │                            |
|   │   (/ws/office-kit)            │   │   SQLite (Dev) / PostGIS (Prod│                            |
|   └───────────────┬───────────────┘   └───────────────────────────────┘                            |
+-------------------┼--------------------------------------------------------------------------------+
                    │ WebSocket / JSON Envelope
                    ▼
+----------------------------------------------------------------------------------------------------+
|                                  OFFICE KIT OBSERVATION CONSOLE                                    |
|                                                                                                    |
|   - Real-Time Device Health & Connection Card                                                      |
|   - Live IMU & Environmental Telemetry Charts                                                      |
|   - Expert Execution Waterfall Timeline (Latency & Status)                                         |
|   - Evidence-Cited Hazard & Alert Incident Feed                                                    |
|   - Spatial Map Visualization with Real Coordinates                                                |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Technology Stack & Runtime Environment

| Subsystem | Technology | Rationale & Configuration |
| :--- | :--- | :--- |
| **Backend Framework** | Python 3.12, FastAPI, Uvicorn | High-throughput async I/O, native WebSockets, Pydantic V2 schema validation. |
| **Data Persistence** | SQLAlchemy 2.0 Async | Dual-target architecture: `sqlite+aiosqlite` for zero-friction local execution; `postgresql+asyncpg` with PostGIS for production deployment via `DATABASE_URL`. |
| **Observation Console** | React 19, TypeScript, Vite | Sub-millisecond reactive rendering, dark-mode glassmorphic interface, real-time WebSocket client. |
| **Mobile Client** | Android Kotlin, Jetpack Compose | Native hardware sensor access (CameraX, FusedLocationProvider, SensorManager), Room SQLite offline store. |
| **Edge Vision Inference**| TFLite / ONNX Runtime Mobile | Validated edge runtimes with graceful fallback when model binaries are uninitialized. |

---

## 4. Phase-by-Phase Implementation Plan

### Phase 1: Environment Audit & Architecture Deliverables [COMPLETED]
- Audited system tools: Python 3.12.10, Node.js 24.21.0, OpenJDK 17.0.18, Git 2.56.0.
- Audited agentic skills catalog (2,560 skills) and established relevant skills.
- Delivered foundational architecture documentation in `docs/`:
  - [`docs/ARCHITECTURE.md`](file:///c:/streetsense/docs/ARCHITECTURE.md)
  - [`docs/EXPERT_SYSTEM.md`](file:///c:/streetsense/docs/EXPERT_SYSTEM.md)
  - [`docs/DATA_MODEL.md`](file:///c:/streetsense/docs/DATA_MODEL.md)
  - [`docs/REALTIME_PROTOCOL.md`](file:///c:/streetsense/docs/REALTIME_PROTOCOL.md)
  - [`docs/FAILURE_MODES.md`](file:///c:/streetsense/docs/FAILURE_MODES.md)
  - [`docs/SECURITY.md`](file:///c:/streetsense/docs/SECURITY.md)
  - [`docs/TESTING.md`](file:///c:/streetsense/docs/TESTING.md)
  - [`docs/RUNBOOK.md`](file:///c:/streetsense/docs/RUNBOOK.md)

---

### Phase 2: Core Contracts, Common Data Schemas & Protocols
**Goal:** Define typed, strictly validated schemas shared across Edge, Backend, and Console.

- **Files to Create:**
  - `backend/app/schemas/sensors.py`: `SensorSnapshot`, `SensorType`, `SensorAccuracy`, `Orientation`.
  - `backend/app/schemas/experts.py`: `ExpertRequest`, `ExpertResult`, `ExecutionStatus`, `ModelProvenance`.
  - `backend/app/schemas/evidence.py`: `EvidenceItem`, `EvidenceType`, `QualityScore`.
  - `backend/app/schemas/events.py`: `DetectedEvent`, `EventSeverity`, `ConfidenceBreakdown`, `AlertTier`.
  - `backend/app/schemas/transport.py`: `WsMessageEnvelope`, `EventType`, `DeviceStatusPayload`.
- **Validation Criteria:**
  - Automated round-trip JSON serialization and validation tests.
  - Zero tolerance for undefined or polymorphic fields without tagged unions.

---

### Phase 3: Real-Time Backend & Storage Layer
**Goal:** Implement the async database models, repositories, authentication, and REST APIs.

- **Files to Create:**
  - `backend/requirements.txt`: FastAPI, Uvicorn, SQLAlchemy>=2.0, aiosqlite, asyncpg, pydantic, python-jose, passlib, pytest, pytest-asyncio.
  - `backend/app/core/config.py`: Environment configuration with dual-target `DATABASE_URL`.
  - `backend/app/core/security.py`: JWT token creation, password hashing, device API key verification.
  - `backend/app/db/session.py`: Async engine, sessionmaker, base declarative class.
  - `backend/app/db/models.py`: Database models (`DeviceModel`, `SessionModel`, `SensorSnapshotModel`, `ExpertRunModel`, `EvidenceModel`, `EventModel`, `AlertModel`, `LocationModel`).
  - `backend/app/db/repositories.py`: Async CRUD operations for all entities.
  - `backend/app/db/init_db.py`: Async database table initialization.
  - `backend/app/api/v1/auth.py`: Token generation and user authentication.
  - `backend/app/api/v1/devices.py`: Device registration and status reporting.
  - `backend/app/api/v1/sessions.py`: Session lifecycle management.
  - `backend/app/api/v1/events.py`: Historical event queries and alert retrieval.
  - `backend/app/main.py`: FastAPI app initialization, middleware, lifecycle events.
- **Validation Criteria:**
  - `pytest backend/tests/test_db_and_api.py` passes with 100% green status on real SQLite/PostgreSQL.

---

### Phase 4: Real-Time Transport Gateway (WebSockets)
**Goal:** Implement bi-directional streaming between edge devices, backend pub/sub, and observation consoles.

- **Files to Create:**
  - `backend/app/websocket/manager.py`: Connection tracking, session rooms, ping/pong heartbeats, sequence deduplication cache.
  - `backend/app/websocket/endpoints.py`:
    - `/ws/telemetry`: Authenticated mobile edge ingress. Validates messages, triggers persistence, and dispatches to broadcast hub.
    - `/ws/office-kit`: Public/authenticated observation console egress. Emits live device health, telemetry, expert execution waterfalls, and alerts.
- **Validation Criteria:**
  - Concurrent WebSocket integration tests verifying message dispatch, disconnection cleanup, and deduplication.

---

### Phase 5: Core Expert Logic & Multi-Modal Fusion Engine
**Goal:** Implement the selective multi-expert orchestration core, baseline specialists, fusion, and arbitration.

- **Files to Create:**
  - `backend/app/engine/base.py`: Abstract `Expert` base class, metadata schemas, and contracts.
  - `backend/app/engine/registry.py`: Capability-based `ExpertRegistry`.
  - `backend/app/engine/experts/sensor_quality.py`: Evaluates sampling frequency jitter, sensor dropouts, noise variance.
  - `backend/app/engine/experts/motion.py`: Evaluates kinetic acceleration magnitude, jerk, sudden stops, pedestrian falls.
  - `backend/app/engine/experts/location.py`: Evaluates GPS accuracy, velocity, bearing deviation, geofencing.
  - `backend/app/engine/experts/illumination.py`: Evaluates ambient lux, overexposure, low-light visibility.
  - `backend/app/engine/experts/vision_object.py`: Edge CV wrapper for ONNX/TFLite object detection with real bounds, confidence, and safe degradation.
  - `backend/app/engine/experts/temporal_change.py`: Evaluates persistence of hazards across sliding temporal windows.
  - `backend/app/engine/fusion.py`: `EvidenceFusionEngine` correlating spatial, kinetic, visual, and temporal evidence.
  - `backend/app/engine/arbitration.py`: `ArbitrationEngine` calculating cross-expert agreement and resolving conflicts.
  - `backend/app/engine/router.py`: `SelectiveExpertRouter` driving capability selection based on energy, latency, and ambiguity.
  - `backend/app/engine/reasoning.py`: `LocalReasoningExpert` generating grounded, evidence-cited natural language explanations.
- **Validation Criteria:**
  - Complete unit test suite verifying deterministic routing, fusion math, arbitration logic, and escalation triggers.

---

### Phase 6: Office Kit Real-Time Observation Console
**Goal:** Build the desktop/web observation console in React + TypeScript + Vite.

- **Files to Create:**
  - `office-kit/package.json`: React 19, TypeScript, Lucide icons, Vite, TailwindCSS / CSS design tokens.
  - `office-kit/vite.config.ts`: Vite dev server configuration with proxy to backend.
  - `office-kit/src/types/protocol.ts`: TypeScript interfaces matching backend schemas.
  - `office-kit/src/services/websocket.ts`: Robust WebSocket client with auto-reconnect and heartbeat tracking.
  - `office-kit/src/components/Header.tsx`: System branding, server connection status, latency pill.
  - `office-kit/src/components/DeviceStatusCard.tsx`: Connected device ID, battery, thermal status, active sensor pills.
  - `office-kit/src/components/TelemetryChart.tsx`: Live 3-axis IMU acceleration, gyroscope, and lux streams.
  - `office-kit/src/components/ExpertExecutionTimeline.tsx`: Waterfall visualization of active experts, execution latency, and confidence.
  - `office-kit/src/components/AlertIncidentFeed.tsx`: Live stream of detected hazards with evidence citations and reasoning explanations.
  - `office-kit/src/components/SpatialMap.tsx`: Live coordinate and heading tracker with real geospatial pins.
  - `office-kit/src/App.tsx`: Master responsive glassmorphic dashboard layout.
- **Validation Criteria:**
  - `npm run build` succeeds with zero TypeScript or bundling errors.
  - Live WebSocket stream verification: charts, expert waterfalls, and incident feeds update dynamically upon message arrival.

---

### Phase 7: Android Native Mobile Application
**Goal:** Build the native Kotlin + Jetpack Compose mobile client targeting Android 14+ (API 34).

- **Files to Create:**
  - `android/settings.gradle.kts` & `android/build.gradle.kts`: Multi-module Gradle configuration.
  - `android/app/build.gradle.kts`: Android application build file with CameraX, Room, Coroutines, OkHttp, Compose BOM.
  - `android/app/src/main/AndroidManifest.xml`: Permissions (`CAMERA`, `ACCESS_FINE_LOCATION`, `BODY_SENSORS`, `VIBRATE`, `INTERNET`).
  - `android/app/src/main/java/io/streetsense/domain/model/`: Shared Kotlin domain models matching JSON protocol schemas.
  - `android/app/src/main/java/io/streetsense/sensors/`:
    - `SensorManagerService.kt`: Accelerometer, Gyroscope, Magnetometer, Light sensor managers.
    - `LocationService.kt`: FusedLocationProviderClient with real GPS updates.
    - `CameraAnalysisService.kt`: CameraX `ImageAnalysis.Analyzer` with backpressure and luminance extraction.
  - `android/app/src/main/java/io/streetsense/engine/`:
    - `SensorNormalizer.kt`: Normalizes raw hardware events into structured `SensorSnapshot`.
    - `TemporalRingBuffer.kt`: Sliding buffer of recent observations.
    - `OnDeviceRouter.kt` & Native Expert Implementations.
  - `android/app/src/main/java/io/streetsense/data/`:
    - Room database (`AppDatabase.kt`, `EventDao.kt`, `SyncQueueDao.kt`).
    - `StreetSenseWebSocketClient.kt`: OkHttp WebSocket transport with auto-reconnect.
  - `android/app/src/main/java/io/streetsense/ui/`:
    - `MainSensingActivity.kt` & Compose UI screens: HUD preview, sensor gauges, active expert pills, alert banner with haptic feedback.
- **Validation Criteria:**
  - Clean Gradle project structure, valid manifest, and verified Kotlin models matching the protocol specification.

---

### Phase 8: End-to-End Integration, Live Verification & Hardening
**Goal:** Verify the complete real vertical slice from sensor input to console display.

- **Verification Workflow:**
  1. Initialize database and start FastAPI server (`http://127.0.0.1:8000`).
  2. Launch Office Kit Console (`http://localhost:5173`).
  3. Run the live verification client emitting real sensor data (accelerometer jerk, sudden deceleration, low lux, obstacle detection).
  4. Verify on Office Kit Console:
     - Real-time telemetry charts reflect incoming samples.
     - Expert execution timeline shows exact latency ms and status.
     - Evidence fusion triggers a deterministic hazard event.
     - Local reasoning explanation is rendered with evidence citations.
  5. Inspect backend database: confirm rows are persisted in `devices`, `sessions`, `sensor_snapshots`, `expert_runs`, `evidence_items`, and `events`.
  6. Execute comprehensive test suite:
     ```bash
     cd backend && pytest tests -v
     cd ../office-kit && npm run build
     ```

---

## 5. First Vertical Slice Milestone Specification

The **First Vertical Slice** proves the fundamental architecture with zero mock data:
$$\text{Sensor Input} \to \text{Ring Buffer} \to \text{Motion Expert} \to \text{Evidence Creation} \to \text{Fusion} \to \text{Decision} \to \text{WebSocket} \to \text{DB Persistence} \to \text{Office Kit UI}$$

1. **Input**: Real 3-axis acceleration snapshot ($\ge 2.5g$ kinetic spike followed by sudden arrest).
2. **Preprocessing**: Normalized into `SensorSnapshot` with timestamp, accuracy, and sensor source.
3. **Expert Execution**: `MotionExpert` evaluates kinetic impulse, calculates confidence based on sensor reliability, and emits `MotionEvidenceItem`.
4. **Fusion & Arbitration**: `EvidenceFusionEngine` correlates motion spike with temporal persistence; `ArbitrationEngine` confirms no conflicting baseline sensors.
5. **Decision & Alert**: Deterministic decision generates `PEDESTRIAN_FALL_OR_IMPACT` event (`HIGH_RISK`).
6. **Local Alert**: Triggers local edge haptic alert.
7. **Transport**: Transmitted over WebSocket in an authenticated `WsMessageEnvelope` with correlation ID.
8. **Persistence**: FastAPI backend stores session, sensor snapshot, expert run, evidence, and event in SQLite/PostgreSQL.
9. **Display**: Office Kit console receives event in real time, plots the IMU jerk on the live chart, adds the expert run to the waterfall timeline, and renders the hazard card with evidence citations.
