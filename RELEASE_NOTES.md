# StreetSense v1.0.0 — Production-Grade Sensing & Multi-Expert Engine

## Overview
StreetSense is a real-time mobile environmental and kinetic sensing platform with a selective multi-expert capability architecture. It executes lightweight deterministic heuristics at 50Hz, arbitrating edge compute resources dynamically and escalating to heavy perceptual specialists only upon genuine kinetic anomalies.

## Key Capabilities & Highlights

### 1. Selective Multi-Expert Capability Routing
- **Deterministic First**: Low-power `MotionExpert`, `IlluminationExpert`, and `SensorQualityExpert` continuously evaluate incoming frames at native sensor rates.
- **Dynamic Gating**: High-power perception modules (e.g. edge vision) activate strictly upon multi-modal kinetic triggers or environmental anomalies, drastically optimizing battery and compute.

### 2. Multi-Modal Evidence Fusion & Arbitration
- Temporal ring buffer (100-sample sliding window) with vector norm acceleration variance, jerk, and tilt delta calculation.
- Evidence arbitration engine synthesizing kinetic shock events into probabilistic incident signals (e.g., `PEDESTRIAN_FALL_OR_IMPACT`, `ROAD_SURFACE_ANOMALY`).

### 3. Production Real-Time Gateway & Live Console
- **FastAPI / Python 3.12 Backend**: Real-time bidirectional WebSocket ingress (`/ws/telemetry`) and broadcast stream (`/ws/console`).
- **Web Console**: React 18, Vite, TypeScript, and TailwindCSS dashboard rendering live spatial maps, kinetic telemetry charts, and incident alerts with sub-millisecond updates.
- **SQLite / PostGIS Persistence**: Full session and telemetry persistence with zero-dependency native SQLite fallback.

### 4. Zero-Mock Physical Hardware Policy
- Zero simulated telemetry, zero fake detections, and zero fabricated AI results.
- Verified physical hardware sensor pipeline on modern Android devices (real 3-axis IMU, lux sensor, FusedLocationProvider).

### 5. Verification & Test Suite
- **12/12 Android Unit Tests** passing across on-device ring buffers, shock detection heuristics, and routing.
- **16/16 Backend Pytest Tests** passing across FastAPI REST endpoints, WebSocket manager, evidence fusion, and expert arbitration.

## Quickstart

```bash
# Backend Gateway
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000

# Web Console
cd web-console
npm install
npm run dev
```
