# StreetSense — Testing Strategy & Verification Plan

## 1. Testing Philosophy

StreetSense is a mission-critical edge sensing and alerting platform. Testing must guarantee:
1. **Mathematical & Contractual Correctness**: Evidence models, confidence breakdowns, and fusion formulas must yield deterministic, reproducible outputs.
2. **Deterministic Routing Integrity**: The selective expert router must strictly adhere to energy and latency constraints without unnecessary escalation.
3. **No Mocking of Missing Features**: Tests must verify real implementations; features marked not implemented must fail safely with explicit status codes.
4. **Transport Resiliency**: Real-time WebSocket protocol must recover from disconnects, reject duplicates, and maintain monotonically ordered event timelines.

---

## 2. Test Pyramid & Coverage Matrix

```
       / \
      / E2E \       End-to-End Pipeline: Sensor -> Router -> Fusion -> WS -> Console
     /-------\
    / Transp. \     WebSocket Reconnect, Handshake, Sequence Deduplication
   /-----------\
  / Integration \   FastAPI REST APIs, Database Persistence, PostGIS Queries
 /---------------\
/   Unit & Math   \ Expert Contracts, Fusion Formulas, Arbitration, Routing Rules
-------------------
```

### Coverage Areas

| Category | Target Subsystem | Verification Scope |
| :--- | :--- | :--- |
| **Unit & Logic** | `SelectiveExpertRouter` | Verify expert selection matches evidence levels; prevent escalation when baseline is normal |
| **Unit & Logic** | `EvidenceFusionEngine` | Verify correlation of optical bounding box + IMU velocity + temporal persistence |
| **Unit & Logic** | `ArbitrationEngine` | Verify conflict resolution when visual and kinetic experts produce opposing predictions |
| **Unit & Logic** | `ConfidenceModel` | Verify multi-factor confidence computation and degradation thresholds |
| **Backend Integration** | `FastAPI REST APIs` | Device registration, session lifecycle, token generation, health endpoints |
| **Transport Integration**| `WebSocket Gateway` | Ingestion of telemetry envelopes, deduplication via `message_id`, broadcast to observation clients |
| **Persistence Integration**| `PostgreSQL/SQLite` | CRUD operations for events, evidence items, and PostGIS location tracking |
| **Failure Path** | `Degraded States` | Disconnected sensors, model timeouts, malformed frames, network dropouts |

---

## 3. Automated Test Execution Commands

### Backend & Core Logic Test Suite
```bash
# Execute unit, integration, and websocket transport tests
pytest backend/tests -v --durations=10

# Test database and repository contracts
pytest backend/tests/test_database.py -v

# Test expert orchestration and evidence fusion
pytest backend/tests/test_fusion_and_routing.py -v

# Test real-time WebSocket protocol and deduplication
pytest backend/tests/test_websocket_transport.py -v
```

### Android Client Test Suite
```bash
# Execute Android local unit tests (Robolectric / JUnit 5)
./gradlew testDebugUnitTest --continue

# Verify Android architecture contracts & lint
./gradlew lintDebug
```

### Console Web Client Suite
```bash
cd web-console
npm run lint
npm run build
```
