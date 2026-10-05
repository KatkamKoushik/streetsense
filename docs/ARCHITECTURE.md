# StreetSense — System Architecture

## 1. Executive Summary & Vision

StreetSense is a real-time mobile environmental and activity sensing platform featuring a **Selective Multi-Expert Architecture**. Rather than executing a monolithic, energy-draining deep learning pipeline on every camera frame and sensor tick, StreetSense employs an evidence-first, capability-driven router that executes lightweight, deterministic specialists first, progressively escalating to multi-modal fusion, expensive edge models, and local reasoning only when environmental evidence justifies it.

The platform spans three primary tiers:
1. **Real-time Mobile Client (Android / Kotlin / Jetpack Compose / CameraX / Sensor APIs)**:
   - Lifecycle-safe sensor streams (Accelerometer, Gyroscope, Magnetometer, Ambient Light, Fused Location).
   - CameraX frame capture with adaptive sampling, frame quality checks, and backpressure management.
   - Sensor normalization engine producing timestamped, high-precision snapshots.
   - Local temporal ring-buffer for multi-frame and temporal persistence analysis.
   - On-device selective expert routing and execution.
   - Evidence fusion, conflict arbitration, escalation engine, and deterministic decision engine.
   - Real-time local alerting (haptic feedback, audio/voice cues, visual HUD).
   - Offline-first SQLite persistence and reliable background sync queue.
2. **Real-time Backend Gateway & Processing Engine (FastAPI / WebSockets / PostgreSQL + PostGIS / Redis)**:
   - Device and session registration, cryptographic authentication (JWT / API tokens).
   - Bi-directional WebSocket real-time transport with heartbeat, backpressure, and reconnection recovery.
   - Ingestion and persistence of normalized sensor snapshots, expert execution telemetry, evidence traces, and hazard events.
   - PostGIS spatial indexing for geospatial queries and proximity fences.
   - Event pub/sub bus broadcasting live telemetry to connected observation clients.
3. **Office Kit Observation Console (Vite / React / TypeScript / Modern High-Performance UI)**:
   - Live stream visualization of connected devices, active sessions, and hardware telemetry.
   - Real-time timeline of expert activations, inference latencies, confidence metrics, and evidence graphs.
   - Interactive spatial map displaying device trajectory and localized hazard detections.
   - Alert management console with audio notifications and operator acknowledgement controls.
   - Zero mock data: true real-time streaming state with explicit empty/disconnected/degraded indicators.

---

## 2. High-Level System Architecture Diagram

```mermaid
graph TD
    subgraph MobileDevice ["Android Mobile Device (StreetSense Edge Client)"]
        subgraph HardwareSensors ["Hardware Sensing Layer"]
            CAM[CameraX Preview/Analysis]
            IMU[Accelerometer & Gyroscope]
            MAG[Magnetometer / Compass]
            LIGHT[Ambient Light Sensor]
            GPS[Fused Location Provider]
        end

        subgraph Preprocessing ["Sensing & Temporal Layer"]
            SQ[Sensor Quality & Normalizer]
            TB[Temporal Ring Buffer (History)]
        end

        subgraph Orchestration ["Selective Multi-Expert Engine"]
            ER[Expert Registry]
            SR[Selective Expert Router]
            EX_CHEAP[Level 1: Motion, Location, SensorQuality Experts]
            EX_VISION[Level 2: Vision, Road, Scene Experts]
            FUSION[Evidence Fusion Engine]
            ARB[Conflict Arbitration Engine]
            ESC[Escalation Engine]
            DEC[Deterministic Decision Layer]
            REASON[Local Reasoning & Explanation]
        end

        subgraph EdgeAction ["Local Action & Persistence"]
            ALERT[Local Alert Engine: Haptic / Voice / HUD]
            ROOM[Local Event & Sync Queue (SQLite/Room)]
        end
    end

    subgraph BackendInfrastructure ["StreetSense Backend Platform"]
        WS_GW[Real-time WebSocket Gateway]
        REST_API[FastAPI REST API Engine]
        AUTH[Auth & Device Registry]
        EVENT_BUS[Pub/Sub Real-time Event Bus]
        DB[(PostgreSQL + PostGIS)]
        CACHE[(Redis State & Pub/Sub)]
    end

    subgraph OfficeKitConsole ["Office Kit Observation Console (Web / Operator)"]
        DASH[Live Device & Session Monitor]
        HUD[Telemetry & Sensor HUD]
        EVD_GRAPH[Evidence & Expert Timeline]
        MAP[PostGIS Spatial Hazard Map]
        ALERT_MON[Incident & Alert Management]
    end

    %% Mobile Data Flow
    HardwareSensors --> SQ
    SQ --> TB
    TB --> SR
    SR -->|Capability Routing| ER
    ER --> EX_CHEAP
    EX_CHEAP -->|Evidence Generated| FUSION
    FUSION -->|Uncertainty / Threshold Trigger| ESC
    ESC -->|Escalate| EX_VISION
    EX_VISION --> FUSION
    FUSION --> ARB
    ARB --> DEC
    DEC --> REASON
    DEC --> ALERT
    DEC --> ROOM
    ROOM -->|Authenticated Sync / Live Stream| WS_GW

    %% Backend Flow
    WS_GW <--> REST_API
    REST_API --> AUTH
    REST_API --> EVENT_BUS
    REST_API --> DB
    EVENT_BUS <--> CACHE

    %% Office Kit Flow
    EVENT_BUS -->|Live Event Stream| OfficeKitConsole
    REST_API -->|Historical & Session Queries| OfficeKitConsole
```

---

## 3. Component Dependency Graph

```mermaid
graph LR
    subgraph CoreContracts ["1. Shared Contracts & Schemas"]
        SCHEMA_SENSORS[Sensor Snapshot Schema]
        SCHEMA_EVIDENCE[Evidence & Expert Contracts]
        SCHEMA_EVENTS[Event & Alert Contracts]
        SCHEMA_WS[WebSocket Transport Protocol]
    end

    subgraph BackendLayer ["2. Backend Infrastructure"]
        DB_MODELS[PostgreSQL/PostGIS Models]
        DB_MIGRATIONS[Alembic Migrations]
        REPO[Repository Layer]
        API_AUTH[Security & Token Auth]
        API_ROUTES[REST Endpoints]
        WS_MANAGER[WebSocket Real-time Manager]
    end

    subgraph MobileLayer ["3. Mobile Edge Client"]
        M_SENSORS[Hardware Sensor Managers]
        M_CAMERA[CameraX Image Analysis]
        M_TEMP_BUF[Temporal Observation Buffer]
        M_EXPERTS[Expert Registry & Implementations]
        M_FUSION[Evidence Fusion Engine]
        M_ARBITRATION[Conflict Arbitration Engine]
        M_ROUTER[Selective Expert Router]
        M_ALERT[Haptic & TTS Alerting]
        M_SYNC[Offline Sync & WS Client]
    end

    subgraph ConsoleLayer ["4. Office Kit Console"]
        UI_WS[WebSocket Client & State Store]
        UI_MAP[Leaflet/MapLibre Spatial View]
        UI_COMPONENTS[Telemetry, Timeline & Alert HUD]
    end

    CoreContracts --> BackendLayer
    CoreContracts --> MobileLayer
    CoreContracts --> ConsoleLayer
    DB_MODELS --> REPO
    REPO --> API_ROUTES
    WS_MANAGER --> API_ROUTES
    M_SENSORS --> M_TEMP_BUF
    M_CAMERA --> M_TEMP_BUF
    M_TEMP_BUF --> M_ROUTER
    M_ROUTER --> M_EXPERTS
    M_EXPERTS --> M_FUSION
    M_FUSION --> M_ARBITRATION
    M_ARBITRATION --> M_ALERT
    M_ARBITRATION --> M_SYNC
    M_SYNC -.->|Real-time Socket| WS_MANAGER
    WS_MANAGER -.->|Real-time Socket| UI_WS
```

---

## 4. Selective Multi-Expert Routing & Escalation Model

```mermaid
stateDiagram-v2
    [*] --> SENSING_IDLE: Device Started
    SENSING_IDLE --> PREPROCESSING: Sensor / Frame Tick

    state PREPROCESSING {
        [*] --> CheckSensorQuality
        CheckSensorQuality --> NormalizeSnapshots
        NormalizeSnapshots --> AppendTemporalBuffer
    }

    PREPROCESSING --> LEVEL_0_SENSOR_CHECK

    state LEVEL_0_SENSOR_CHECK {
        [*] --> EvaluateBaselines
        EvaluateBaselines --> MotionBaseline
        EvaluateBaselines --> IlluminationBaseline
    }

    LEVEL_0_SENSOR_CHECK --> ROUTER: Baseline Metrics Ready

    state ROUTER {
        [*] --> SelectExperts
        note right of SelectExperts: Evaluates energy, latency, current evidence needs
    }

    ROUTER --> LEVEL_1_CHEAP_EXPERTS: Low to moderate anomaly
    ROUTER --> SENSING_IDLE: Normal environment (No escalation required)

    state LEVEL_1_CHEAP_EXPERTS {
        [*] --> MotionExpert
        [*] --> LocationExpert
        [*] --> SensorQualityExpert
    }

    LEVEL_1_CHEAP_EXPERTS --> EVIDENCE_FUSION_1

    state EVIDENCE_FUSION_1 {
        [*] --> CorrelateEvidence
        CorrelateEvidence --> ComputeConfidenceAgreement
    }

    EVIDENCE_FUSION_1 --> ARBITRATION: High Agreement & Certainty
    EVIDENCE_FUSION_1 --> LEVEL_2_ESCALATION: Uncertainty / Ambiguity / Visual Need

    state LEVEL_2_ESCALATION {
        [*] --> ObjectDetectionExpert
        [*] --> RoadAnalysisExpert
        [*] --> SceneExpert
    }

    LEVEL_2_ESCALATION --> EVIDENCE_FUSION_2

    state EVIDENCE_FUSION_2 {
        [*] --> MultiModalFusion
    }

    EVIDENCE_FUSION_2 --> ARBITRATION

    state ARBITRATION {
        [*] --> DetectConflict
        DetectConflict --> ResolveOrMarkUncertain
    }

    ARBITRATION --> DECISION_ENGINE

    state DECISION_ENGINE {
        [*] --> DeterministicThresholds
        DeterministicThresholds --> GenerateExplanation
    }

    DECISION_ENGINE --> ALERTING: Hazard Verified
    DECISION_ENGINE --> DISPATCH_TELEMETRY: Logged & Streamed

    ALERTING --> DISPATCH_TELEMETRY
    DISPATCH_TELEMETRY --> SENSING_IDLE
```

---

## 5. Deployment Topology

```mermaid
graph TB
    subgraph Edge ["Edge Environment"]
        subgraph Phone ["Physical Android Device"]
            APK["StreetSense Mobile App"]
            CAMERA["Hardware Camera (CameraX)"]
            IMU_DEV["IMU / Accelerometer / Gyro"]
            GPS_DEV["GPS Receiver"]
            SQLITE_DEV[("Local SQLite / Room")]
        end
    end

    subgraph Cloud ["Server Environment (Docker / Production / Local)"]
        subgraph EdgeGateway ["Network Ingress"]
            NGINX["Reverse Proxy / TLS Terminator (Port 443 / 80)"]
        end

        subgraph AppServices ["Application Tier"]
            FASTAPI["FastAPI Async Server (Uvicorn Workers)"]
            WS_HUB["WebSocket Broadcast Hub"]
        end

        subgraph DataTier ["Data & State Tier"]
            POSTGRES[("PostgreSQL 16 + PostGIS")]
            REDIS[("Redis 7 (Pub/Sub & Session Cache)")]
        end
    end

    subgraph Operator ["Monitoring & Operations"]
        BROWSER["Operator Workstation (Office Kit Console)"]
    end

    APK -->|WSS / HTTPS| NGINX
    BROWSER -->|WSS / HTTPS| NGINX
    NGINX --> FASTAPI
    FASTAPI <--> WS_HUB
    FASTAPI <--> POSTGRES
    FASTAPI <--> REDIS
    WS_HUB <--> REDIS
```
