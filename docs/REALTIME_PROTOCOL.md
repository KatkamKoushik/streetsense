# StreetSense — Real-Time WebSocket Protocol Specification

## 1. Transport Overview

The StreetSense real-time transport coordinates low-latency, bidirectional telemetry and event streaming between:
- **Mobile Edge Clients** (Android devices transmitting sensor observations and fused hazard events)
- **StreetSense Backend Gateway** (Authenticating identity, enforcing guardrails, persisting records)
- **Web Observation Consoles** (Receiving real-time alerts and telemetry broadcasts)

Transport Technology:
- Primary: **RFC 6455 WebSocket** over TLS (`wss://`)
- Ports: Default 8000 (development), 443 (production)

---

## 2. Authentication Handshake & Transport Modes

Before any telemetry or observation message is processed, the WebSocket connection must be cryptographically authenticated. StreetSense supports three standard transport methods:

### Mode 1: HTTP Authorization Header (Native Clients)
```http
GET /ws/telemetry HTTP/1.1
Host: api.streetsense.io
Upgrade: websocket
Connection: Upgrade
Authorization: Bearer <JWT_DEVICE_TOKEN>
```

### Mode 2: Sec-WebSocket-Protocol (Header-Restricted Clients)
```http
GET /ws/telemetry HTTP/1.1
Host: api.streetsense.io
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Protocol: bearer.<JWT_DEVICE_TOKEN>
```

### Mode 3: First-Frame Authentication Envelope (Web Browsers)
For clients that cannot customize WebSocket request headers, connect to `/ws/telemetry` or `/ws/console` directly and transmit the first frame within 5.0 seconds:
```json
{
  "event_type": "auth",
  "token": "<JWT_ACCESS_TOKEN>"
}
```
Upon successful validation, the gateway responds with an authentication acknowledgement frame:
```json
{
  "event_type": "auth.success",
  "status": "authenticated",
  "subject": "pixel_8_pro_edge_01"
}
```
If the token is invalid, expired, or timed out, the server emits `auth.error` and closes the socket with code `4401 Policy Violation`.

---

## 3. Message Envelope & Wire Format

Every WebSocket frame is serialized as UTF-8 JSON complying with `WsMessageEnvelope`:

```json
{
  "message_id": "msg_1728143523000",
  "correlation_id": "corr_849102",
  "session_id": "sess_849102",
  "device_id": "pixel_8_pro_edge_01",
  "timestamp_ns": 1728143523000000000,
  "event_type": "event.detected",
  "sequence_number": 42,
  "payload": {
    "event": {
      "event_id": "evt_fall_001",
      "session_id": "sess_849102",
      "timestamp_ns": 1728143523000000000,
      "category": "PEDESTRIAN_FALL_OR_IMPACT",
      "severity": "HIGH_RISK",
      "confidence_breakdown": {
        "prediction_confidence": 0.92,
        "input_quality": 0.95,
        "temporal_consistency": 0.88,
        "sensor_reliability": 0.99,
        "cross_expert_agreement": 0.90,
        "geometric_consistency": 0.85,
        "evidence_quality": 0.92,
        "final_decision_confidence": 0.91
      },
      "contributing_evidence_ids": ["ev_accel_peak", "ev_impact_shock"],
      "explanation": "High kinetic deceleration spike detected by MotionExpert.",
      "haptic_pattern": "STRONG_DOUBLE_PULSE",
      "is_dismissed": false
    }
  }
}
```

### Envelope Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `message_id` | String | Unique frame identifier for deduplication |
| `correlation_id` | String | Distributed trace identifier correlating input tick to detection and alert |
| `session_id` | String | Active session identifier (must belong to authenticated device) |
| `device_id` | String | Device identifier (must strictly match authenticated token subject) |
| `timestamp_ns` | Int (64-bit) | Epoch nanoseconds when reading was captured at edge |
| `event_type` | String | Canonical event classification |
| `sequence_number` | Int | Strictly monotonically increasing sequence number |
| `payload` | Object | Typed data dictionary corresponding to `event_type` |

---

## 4. Ingress Guardrails & Rejection Error Codes

The gateway evaluates every frame against the following security gates:

| Condition | Error Code | Response Message | Connection Action |
| :--- | :--- | :--- | :--- |
| Payload Size > 64 KB | 4413 | `Payload size exceeds 64KB ceiling` | Closes socket |
| Rate Limit > 1200 msg/min | 4429 | `Rate limit exceeded. Maximum 1200 messages/minute.` | Closes socket |
| Malformed JSON / Schema mismatch | 4400 | `Malformed envelope or invalid schema` | Closes socket |
| Unapproved Event Type | 4403 | `Event type is not permitted` | Drops frame |
| Envelope `device_id` != Token Subject | 4403 | `Identity mismatch: envelope device_id does not match authenticated token subject` | Closes socket |
| Timestamp Skew > 300s | 4400 | `Timestamp skew exceeds 300 seconds` | Drops frame |
| `sequence_number` <= previous seen | 4409 | `Sequence number must be strictly monotonic and greater than prior seen sequence` | Drops frame |
| Session not found / ownership mismatch | 4400 | `Session not found or does not belong to authenticated device` | Drops frame |

---

## 5. Standard Event Allowlist

Only approved telemetry event types are processed on `/ws/telemetry`:
- `sensor.status`: Sensor availability matrix and snapshot batches.
- `device.status`: Hardware telemetry (battery level, battery temperature, thermal state).
- `expert.completed`: Execution outcome of an edge expert run.
- `inference.completed`: End-to-end edge pipeline inference outcome.
- `event.detected`: Deterministic decision engine confirmed an environmental hazard.
- `alert.triggered`: Edge alerted user via Haptic/Audio/HUD.
- `heartbeat.ping`: Bidirectional liveness probe (receives `heartbeat.pong`).
