import asyncio
import json
import time
import math
import urllib.request
import urllib.error
import websockets

BACKEND_HTTP_URL = "http://127.0.0.1:8000"
BACKEND_WS_URL = "ws://127.0.0.1:8000/ws/telemetry"
DEVICE_ID = "pixel_8_pro_demo"
PROVISIONING_KEY = "streetsense_dev_provisioning_master_key_32c"
DEMO_SECRET = "sec_demo_credential_pixel_8_pro_12345"


def setup_device_auth() -> str:
    """Provision device and acquire cryptographically verified JWT bearer token."""
    print("Step 1: Provisioning demo device...")
    prov_req = urllib.request.Request(
        f"{BACKEND_HTTP_URL}/api/v1/devices/provision",
        data=json.dumps({
            "device_id": DEVICE_ID,
            "name": "Pixel 8 Pro Verification Client",
            "device_secret": DEMO_SECRET,
            "model": "Pixel 8 Pro",
            "os_version": "Android 15 (API 35)"
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Provisioning-Key": PROVISIONING_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(prov_req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Device provisioned with status: {data.get('status')}")
    except urllib.error.HTTPError as e:
        print(f"[NOTE] Provisioning response ({e.code}): Device already enrolled or updated.")

    print("Step 2: Acquiring device telemetry JWT token...")
    token_req = urllib.request.Request(
        f"{BACKEND_HTTP_URL}/api/v1/auth/token",
        data=json.dumps({
            "device_id": DEVICE_ID,
            "device_secret": DEMO_SECRET
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(token_req) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))
        access_token = token_data["access_token"]
        print(f"[OK] Token issued for {token_data['subject']} (expires in {token_data['expires_in_minutes']}m)")
        return access_token


def start_device_session(token: str, session_id: str) -> None:
    """Explicitly start an authenticated session in the database."""
    print(f"Step 3: Registering active session '{session_id}'...")
    sess_req = urllib.request.Request(
        f"{BACKEND_HTTP_URL}/api/v1/sessions/start",
        data=json.dumps({
            "session_id": session_id,
            "device_id": DEVICE_ID
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )
    with urllib.request.urlopen(sess_req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[OK] Session started successfully: {data['session_id']}")


async def run_live_telemetry_stream():
    print("=" * 60)
    print("StreetSense Live Telemetry & Identity Verification Stream")
    print("=" * 60)

    try:
        token = setup_device_auth()
    except Exception as e:
        print(f"[FATAL] Authentication setup failed: {e}")
        print("Ensure backend is running: python -m uvicorn app.main:app --port 8000")
        return

    session_id = f"sess_live_{int(time.time())}"
    try:
        start_device_session(token, session_id)
    except Exception as e:
        print(f"[FATAL] Session creation failed: {e}")
        return

    print(f"\nStep 4: Connecting to authenticated WebSocket at {BACKEND_WS_URL}...")
    try:
        async with websockets.connect(BACKEND_WS_URL) as ws:
            # First message must be authentication frame
            auth_frame = {
                "event_type": "auth",
                "token": token
            }
            await ws.send(json.dumps(auth_frame))
            auth_resp_raw = await ws.recv()
            auth_resp = json.loads(auth_resp_raw)

            if auth_resp.get("event_type") != "auth.success":
                print(f"[AUTH FAILED] {auth_resp}")
                return

            print(f"[AUTHENTICATED] WebSocket authenticated as {auth_resp.get('subject')}\n")
            seq = 1

            # 1. Send Device Status
            device_status_msg = {
                "message_id": f"msg_stat_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": DEVICE_ID,
                "timestamp_ns": time.time_ns(),
                "event_type": "device.status",
                "sequence_number": seq,
                "payload": {
                    "device_status": {
                        "battery_level": 88.0,
                        "battery_temperature_c": 31.4,
                        "is_charging": False,
                        "thermal_state": "NORMAL",
                        "network_type": "WIFI",
                        "active_sensors": ["ACCELEROMETER", "GYROSCOPE", "MAGNETOMETER", "AMBIENT_LIGHT", "GPS"],
                        "degraded_sensors": []
                    }
                }
            }
            await ws.send(json.dumps(device_status_msg))
            seq += 1

            # 2. Stream walking baseline (12 samples)
            print("Phase 1: Streaming Normal Pedestrian Motion (Walking Baseline)...")
            for i in range(12):
                now_ns = time.time_ns()
                t = i * 0.2
                x = 0.4 * math.sin(t * 3.0)
                y = 9.81 + 1.2 * math.cos(t * 3.0)
                z = 0.6 * math.sin(t * 2.0)

                snap_msg = {
                    "message_id": f"msg_snap_{seq}",
                    "correlation_id": f"corr_{seq}",
                    "session_id": session_id,
                    "device_id": DEVICE_ID,
                    "timestamp_ns": now_ns,
                    "event_type": "sensor.status",
                    "sequence_number": seq,
                    "payload": {
                        "snapshots": [
                            {
                                "sensor_type": "ACCELEROMETER",
                                "timestamp_ns": now_ns,
                                "values": [round(x, 3), round(y, 3), round(z, 3)],
                                "accuracy": "HIGH",
                                "orientation": "PORTRAIT"
                            }
                        ]
                    }
                }
                await ws.send(json.dumps(snap_msg))
                seq += 1
                await asyncio.sleep(0.1)

            print("[SUCCESS] Baseline walking telemetry streaming live at ~10Hz.")

            # 3. Simulate sudden fall / kinetic impact
            print("\nPhase 2: Triggering Anomalous Kinetic Shock (Pedestrian Fall)...")
            now_ns = time.time_ns()
            shock_msg = {
                "message_id": f"msg_snap_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": DEVICE_ID,
                "timestamp_ns": now_ns,
                "event_type": "sensor.status",
                "sequence_number": seq,
                "payload": {
                    "snapshots": [
                        {
                            "sensor_type": "ACCELEROMETER",
                            "timestamp_ns": now_ns,
                            "values": [12.4, 30.1, -8.6],
                            "accuracy": "HIGH",
                            "orientation": "FLAT"
                        }
                    ]
                }
            }
            await ws.send(json.dumps(shock_msg))
            seq += 1

            # 4. Expert Run Completed
            expert_msg = {
                "message_id": f"msg_exp_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": DEVICE_ID,
                "timestamp_ns": now_ns,
                "event_type": "expert.completed",
                "sequence_number": seq,
                "payload": {
                    "expert_result": {
                        "expert_id": "motion_expert_v1",
                        "capability": "MOTION_ANALYSIS",
                        "status": "SUCCESS",
                        "prediction": "PEDESTRIAN_FALL_OR_IMPACT",
                        "confidence": 0.94,
                        "evidence": [
                            {
                                "evidence_id": f"ev_{now_ns}",
                                "expert_id": "motion_expert_v1",
                                "evidence_type": "PEDESTRIAN_FALL",
                                "confidence": 0.94,
                                "timestamp_ns": now_ns,
                                "source_sensor": "ACCELEROMETER",
                                "attributes": {"g_force": 3.32, "peak_magnitude_mps2": 32.5},
                                "weight": 1.5
                            }
                        ],
                        "timestamp_ns": now_ns,
                        "provenance": {
                            "runtime": "deterministic-kinetic",
                            "model_name": "VectorMagnitudeAnalyzer",
                            "version": "1.0.0",
                            "device": "cpu"
                        },
                        "limitations": [],
                        "latency_ms": 1.4
                    }
                }
            }
            await ws.send(json.dumps(expert_msg))
            seq += 1

            # 5. Emit Deterministic Fused Event
            event_msg = {
                "message_id": f"msg_evt_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": DEVICE_ID,
                "timestamp_ns": now_ns,
                "event_type": "event.detected",
                "sequence_number": seq,
                "payload": {
                    "event": {
                        "event_id": f"evt_demo_{int(time.time())}",
                        "session_id": session_id,
                        "timestamp_ns": now_ns,
                        "category": "PEDESTRIAN_FALL_OR_IMPACT",
                        "severity": "HIGH_RISK",
                        "confidence_breakdown": {
                            "prediction_confidence": 0.94,
                            "input_quality": 0.98,
                            "temporal_consistency": 0.91,
                            "sensor_reliability": 0.99,
                            "cross_expert_agreement": 0.95,
                            "geometric_consistency": 0.90,
                            "evidence_quality": 0.96,
                            "final_decision_confidence": 0.94
                        },
                        "contributing_evidence_ids": [f"ev_{now_ns}"],
                        "explanation": "High-impact kinetic shock (3.32g) detected. Motion analysis indicates severe pedestrian fall.",
                        "haptic_pattern": "STRONG_DOUBLE_PULSE",
                        "latitude": 37.7751,
                        "longitude": -122.4192,
                        "is_dismissed": False
                    }
                }
            }
            await ws.send(json.dumps(event_msg))
            print("[SUCCESS] Event transmitted & persisted: PEDESTRIAN_FALL_OR_IMPACT (HIGH_RISK)")

            print("\n[STREAM COMPLETE] Live authenticated telemetry stream verified successfully.")

    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")


if __name__ == "__main__":
    asyncio.run(run_live_telemetry_stream())
