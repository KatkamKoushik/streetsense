# StreetSense — Operations & Developer Runbook

## 1. System Requirements & Environment

- **Operating System**: Windows 11 / 10, Linux (Ubuntu 22.04+), or macOS
- **Runtimes**:
  - Python 3.12+ (Backend, ML tools, test suites)
  - Node.js 20+ / 24+ & npm (Office Kit Observation Console)
  - OpenJDK 17 LTS (Android build tooling)
  - Android SDK (API 34+ / UpsideDownCake, Build-Tools 34.0.0+)
- **Optional/Production Infrastructure**:
  - PostgreSQL 16 with PostGIS extension
  - Redis 7.2+

---

## 2. Quickstart: Backend & Real-Time Gateway

### Step 1: Initialize Python Virtual Environment & Install Dependencies
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to `.env`:
```ini
ENVIRONMENT=development
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./streetsense.db
# Or for PostgreSQL with PostGIS:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/streetsense
SECRET_KEY=dev_secret_streetsense_key_replace_in_prod_091823
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]
```

### Step 3: Run Database Migrations / Initialize Tables
```bash
python -m app.db.init_db
```

### Step 4: Start FastAPI Server with WebSockets
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation (Swagger UI): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- WebSocket Telemetry Ingress: `ws://localhost:8000/ws/telemetry`
- WebSocket Office Kit Stream: `ws://localhost:8000/ws/office-kit`

---

## 3. Quickstart: Office Kit Observation Console

### Step 1: Install Dependencies
```bash
cd office-kit
pnpm install
```

### Step 2: Launch Console in Development Mode
```bash
pnpm dev
```
Access the console at: `http://localhost:5173`

---

## 4. Production Containerization (Docker)
Once WSL 2 is installed on Windows (`wsl --install`), launch Docker Desktop and run:
```bash
docker compose up -d
```
This spins up:
- PostgreSQL 16 with PostGIS (`port 5432`)
- Redis 7.2 (`port 6379`)
- StreetSense FastAPI Backend (`port 8000`)
- Celery Asynchronous Worker

---

## 4. Quickstart: Android Edge Application

### Step 1: Project Build & Verification
```bash
cd android
./gradlew assembleDebug
```

### Step 2: Deploy to Connected Physical Device or Emulator
```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
Or run directly from Android Studio pointing to `android/` directory.

### Step 3: Live Verification
1. Launch StreetSense on device.
2. Grant Camera and Location permissions.
3. Tap **"Start Sensing"**.
4. Observe real-time kinetic telemetry, camera frame quality, expert execution timeline, and live event transmission to the Office Kit Console.
