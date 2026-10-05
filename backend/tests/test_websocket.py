import pytest
import json
import time
from starlette.testclient import TestClient
from app.main import app
from app.schemas.transport import EventType


def test_websocket_ping_pong():
    client = TestClient(app)
    with client.websocket_connect("/ws/telemetry?device_id=test_phone") as ws:
        ping_envelope = {
            "message_id": "msg_ping_001",
            "correlation_id": "corr_001",
            "session_id": "sess_001",
            "device_id": "test_phone",
            "timestamp_ns": int(time.time_ns()),
            "event_type": EventType.HEARTBEAT_PING.value,
            "sequence_number": 1,
            "payload": {}
        }
        ws.send_text(json.dumps(ping_envelope))
        resp_text = ws.receive_text()
        resp = json.loads(resp_text)
        assert resp["event_type"] == EventType.HEARTBEAT_PONG.value
        assert resp["message_id"] == "pong-msg_ping_001"


def test_websocket_telemetry_broadcast_to_office_kit():
    client = TestClient(app)
    # Observer connects to office kit
    with client.websocket_connect("/ws/office-kit") as observer_ws:
        # Edge device connects to telemetry
        with client.websocket_connect("/ws/telemetry?device_id=edge_device_1") as device_ws:
            event_envelope = {
                "message_id": "event_msg_100",
                "correlation_id": "corr_100",
                "session_id": "sess_broadcast_test",
                "device_id": "edge_device_1",
                "timestamp_ns": int(time.time_ns()),
                "event_type": EventType.EVENT_DETECTED.value,
                "sequence_number": 2,
                "payload": {
                    "event": {
                        "event_id": "evt_test_100",
                        "session_id": "sess_broadcast_test",
                        "timestamp_ns": int(time.time_ns()),
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
                        "contributing_evidence_ids": ["ev_1", "ev_2"],
                        "explanation": "High kinetic deceleration spike detected by MotionExpert.",
                        "haptic_pattern": "STRONG_DOUBLE_PULSE",
                        "is_dismissed": False
                    }
                }
            }
            # Device sends event
            device_ws.send_text(json.dumps(event_envelope))

            # Observer receives broadcast
            received_text = observer_ws.receive_text()
            received = json.loads(received_text)
            assert received["message_id"] == "event_msg_100"
            assert received["event_type"] == EventType.EVENT_DETECTED.value
            assert received["payload"]["event"]["category"] == "PEDESTRIAN_FALL_OR_IMPACT"
