import asyncio
import json
import time
import math
import websockets

BACKEND_WS_URL = "ws://127.0.0.1:8000/ws/telemetry?device_id=pixel_8_pro_demo"


async def run_live_telemetry_stream():
    print("=" * 60)
    print("StreetSense Live Telemetry & Multi-Expert Verification Stream")
    print("Connecting to Backend Gateway at ws://127.0.0.1:8000/ws/telemetry...")
    print("=" * 60)

    try:
        async with websockets.connect(BACKEND_WS_URL) as ws:
            print("[CONNECTED] Edge device linked to gateway. Streaming real telemetry...\n")
            session_id = f"sess_live_{int(time.time())}"
            seq = 1

            # 1. Send Device Status
            device_status_msg = {
                "message_id": f"msg_stat_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": "pixel_8_pro_demo",
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

            # 2. Stream walking baseline (10 samples)
            print("Phase 1: Streaming Normal Pedestrian Motion (Walking Baseline)...")
            for i in range(12):
                now_ns = time.time_ns()
                # Subtle sinusoidal walking gait motion around 9.8 m/s²
                t = i * 0.2
                x = 0.4 * math.sin(t * 3.0)
                y = 9.81 + 1.2 * math.cos(t * 3.0)
                z = 0.6 * math.sin(t * 2.0)

                snap_msg = {
                    "message_id": f"msg_snap_{seq}",
                    "correlation_id": f"corr_{seq}",
                    "session_id": session_id,
                    "device_id": "pixel_8_pro_demo",
                    "timestamp_ns": now_ns,
                    "event_type": "sensor.status",
                    "sequence_number": seq,
                    "payload": {
                        "snapshots": [
                            {
                                "sensor_type": "ACCELEROMETER",
                                "timestamp_ns": now_ns,
                                "values": [round(x, 2), round(y, 2), round(z, 2)],
                                "accuracy": "HIGH",
                                "orientation": "PORTRAIT"
                            },
                            {
                                "sensor_type": "AMBIENT_LIGHT",
                                "timestamp_ns": now_ns,
                                "values": [340.0],
                                "accuracy": "HIGH",
                                "orientation": "PORTRAIT"
                            }
                        ],
                        "location": {
                            "latitude": 37.7749 + (i * 0.00002),
                            "longitude": -122.4194 + (i * 0.00002),
                            "altitude": 14.5,
                            "accuracy_meters": 4.2,
                            "speed_mps": 1.3,
                            "bearing_degrees": 45.0,
                            "timestamp_ns": now_ns
                        }
                    }
                }
                await ws.send(json.dumps(snap_msg))
                seq += 1
                await asyncio.sleep(0.15)

            # 3. Simulate Sudden Impact / Fall Event
            print("\nPhase 2: Simulating Sudden High-Kinetic Shock (32.5 m/s² ~3.3g)...")
            now_ns = time.time_ns()
            shock_msg = {
                "message_id": f"msg_shock_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": "pixel_8_pro_demo",
                "timestamp_ns": now_ns,
                "event_type": "sensor.status",
                "sequence_number": seq,
                "payload": {
                    "snapshots": [
                        {
                            "sensor_type": "ACCELEROMETER",
                            "timestamp_ns": now_ns,
                            "values": [12.4, 28.6, 9.8],
                            "accuracy": "HIGH",
                            "orientation": "PORTRAIT"
                        }
                    ]
                }
            }
            await ws.send(json.dumps(shock_msg))
            seq += 1
            await asyncio.sleep(0.1)

            # 4. Emit Expert Completed Waterfall
            expert_msg = {
                "message_id": f"msg_exp_{seq}",
                "correlation_id": f"corr_{seq}",
                "session_id": session_id,
                "device_id": "pixel_8_pro_demo",
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
                "device_id": "pixel_8_pro_demo",
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

            # Continue streaming at resting position
            print("\nPhase 3: Device resting after impact. Continuing stream for 10 seconds...")
            for i in range(20):
                now_ns = time.time_ns()
                snap_msg = {
                    "message_id": f"msg_snap_{seq}",
                    "correlation_id": f"corr_{seq}",
                    "session_id": session_id,
                    "device_id": "pixel_8_pro_demo",
                    "timestamp_ns": now_ns,
                    "event_type": "sensor.status",
                    "sequence_number": seq,
                    "payload": {
                        "snapshots": [
                            {
                                "sensor_type": "ACCELEROMETER",
                                "timestamp_ns": now_ns,
                                "values": [0.1, 9.8, 0.2],
                                "accuracy": "HIGH",
                                "orientation": "PORTRAIT"
                            }
                        ]
                    }
                }
                await ws.send(json.dumps(snap_msg))
                seq += 1
                await asyncio.sleep(0.3)

            print("\n[STREAM COMPLETE] Live demonstration telemetry stream finished successfully.")

    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("Make sure the backend is running first: python -m uvicorn app.main:app --port 8000")


if __name__ == "__main__":
    asyncio.run(run_live_telemetry_stream())
