# StreetSense — Operations & Developer Runbook

## 1. System Requirements & Hardware Specifications

### Physical Edge Hardware (Mobile Sensing)
- **Minimum Device**: Android 14+ (API Level 34) smartphone.
- **Recommended Device**: Google Pixel 7 / 8 / 9 Pro or equivalent flagship with hardware NPU.
- **Sensors Required**:
  - Tri-axial Accelerometer & Gyroscope (>= 50 Hz sample rate)
  - Ambient Light Sensor
  - GNSS / GPS Receiver with Fine Location
  - Camera (Wide-angle, >= 30 FPS preview stream)
  - Haptic Motor with Waveform Pulse Support

### Server Infrastructure
- **Operating System**: Linux (Ubuntu 22.04 LTS), Windows 11 / Server 2022, macOS
- **Runtime**: Python 3.12+ (Backend & Expert Pipeline)
- **Node.js**: 20+ LTS / npm 10+ (Web Observation Console)
- **Database**: SQLite with aiosqlite (Local development/testing) or PostgreSQL 16 with PostGIS (Production)

---

## 2. Environment Variables & Secret Configuration

Copy `backend/.env.example` to `backend/.env` and configure:

```ini
ENVIRONMENT=development
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./streetsense.db
DATABASE_ECHO=false

# Identity & Cryptography (Must be >= 32 characters; production fails closed if default)
JWT_SECRET=streetsense_super_secret_jwt_key_for_dev_32char
JWT_ALGORITHM=HS256
JWT_ISSUER=streetsense:auth
JWT_AUDIENCE_DEVICE=streetsense:telemetry
JWT_AUDIENCE_CONSOLE=streetsense:console

ACCESS_TOKEN_EXPIRE_MINUTES=1440
CONSOLE_TOKEN_EXPIRE_MINUTES=480

DEVICE_PROVISIONING_KEY=streetsense_dev_provisioning_master_key_32c
CONSOLE_API_KEY=streetsense_dev_console_access_key_32c

# WebSocket Limits
MAX_WS_MESSAGE_SIZE=65536
MAX_TIMESTAMP_SKEW_SECONDS=300
WS_RATE_LIMIT_PER_MINUTE=1200
WS_AUTH_TIMEOUT_SECONDS=5.0
```

---

## 3. Device Provisioning & Key Lifecycle Workflows

### 3.1 Provisioning a New Hardware Device
Provisioning must be executed over an authenticated admin channel:

```bash
curl -X POST http://localhost:8000/api/v1/devices/provision \
  -H "X-Provisioning-Key: streetsense_dev_provisioning_master_key_32c" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pixel_8_edge_001",
    "name": "Field Unit Alpha",
    "model": "Pixel 8 Pro",
    "os_version": "Android 14",
    "app_version": "1.0.0"
  }'
```
Response:
```json
{
  "device_id": "pixel_8_edge_001",
  "name": "Field Unit Alpha",
  "device_secret": "<SECURE_GENERATED_SECRET>",
  "status": "ACTIVE",
  "is_active": true,
  "created_at": "2026-11-05T10:00:00Z"
}
```

### 3.2 Acquiring Device Telemetry Token
The edge device exchanges its provisioned secret for a signed JWT token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "pixel_8_edge_001",
    "api_key": "<SECURE_GENERATED_SECRET>"
  }'
```

### 3.3 Rotating Device Credentials
When credentials near expiration or require routine rotation:
```bash
curl -X POST http://localhost:8000/api/v1/devices/pixel_8_edge_001/rotate-key \
  -H "Content-Type: application/json" \
  -d '{
    "current_secret": "<CURRENT_SECRET>"
  }'
```

### 3.4 Immediate Device Revocation (Incident Response)
To immediately block a compromised or missing unit:
```bash
curl -X POST http://localhost:8000/api/v1/devices/pixel_8_edge_001/revoke \
  -H "X-Provisioning-Key: streetsense_dev_provisioning_master_key_32c"
```

---

## 4. Running Tests & Verifying Guardrails

Execute the complete backend test suite:
```bash
# Windows PowerShell
$env:PYTHONPATH="backend"; pytest backend/tests -v

# Linux / macOS
PYTHONPATH=backend pytest backend/tests -v
```

All 25 test cases verify:
- Cryptographic authentication lifecycle
- Revoked device rejections
- Anonymous WebSocket rejection
- Sequence number replay rejection
- Application-level payload size limits (>64 KB)
- Live database readiness reporting (`/ready` probe)

---

## 5. Web Console Verification

To build and run the Web Observation Console:
```bash
cd web-console
npm install
npm run build
npm run dev
```
Access the dashboard at `http://localhost:5173`.
