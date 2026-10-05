import math
import time
from typing import Set, List
from app.engine.base import BaseExpert
from app.schemas.experts import (
    ExpertCapability, ExecutionStatus, ExpertRequest, ExpertResult, ModelProvenance
)
from app.schemas.sensors import SensorType, SensorSnapshot
from app.schemas.evidence import EvidenceType


class MotionExpert(BaseExpert):
    def __init__(self):
        super().__init__(
            expert_id="motion_expert_v1",
            capability=ExpertCapability.MOTION_ANALYSIS,
            required_sensors={SensorType.ACCELEROMETER},
            estimated_latency_ms=1.2,
            estimated_energy_cost="LOW"
        )

    def is_available(self) -> bool:
        return True

    async def execute(self, request: ExpertRequest) -> ExpertResult:
        start_t = time.perf_counter()
        now_ns = time.time_ns()

        accel_snapshots: List[SensorSnapshot] = [
            s for s in request.sensor_snapshots if s.sensor_type == SensorType.ACCELEROMETER
        ]

        if not accel_snapshots:
            return self.create_fallback_result(
                ExecutionStatus.UNAVAILABLE,
                "No accelerometer snapshots provided in request"
            )

        evidence_list = []
        max_magnitude = 0.0
        magnitudes = []
        has_glitch = False
        glitch_reason = None
        valid_sample_count = 0

        for s in accel_snapshots:
            if len(s.values) < 3 or any(math.isnan(v) or math.isinf(v) for v in s.values):
                has_glitch = True
                glitch_reason = "Corrupted accelerometer sample with NaN/Infinite or insufficient axes"
                continue

            if s.timestamp_ns <= 0:
                has_glitch = True
                glitch_reason = f"Invalid sensor timestamp ({s.timestamp_ns} <= 0)"
                continue

            x, y, z = s.values[0], s.values[1], s.values[2]
            mag = math.sqrt(x * x + y * y + z * z)

            # Hardware range and glitch validation:
            # Standard mobile IMU saturates around 16g (~157 m/s²).
            # Any reading > 200 m/s² or exceeding hardware maximumRange is an unphysical spike/glitch.
            max_range = getattr(s, "max_range", None)
            is_out_of_range = (max_range is not None and mag > max_range * 1.05) or (mag > 200.0)

            if is_out_of_range or not getattr(s, "is_valid", True):
                has_glitch = True
                glitch_reason = f"Out-of-range sensor spike detected: {mag:.2f} m/s² (hardware max: {max_range or 200} m/s²). Filtered to prevent false incident."
                continue

            valid_sample_count += 1
            magnitudes.append(mag)
            if mag > max_magnitude:
                max_magnitude = mag

        if valid_sample_count == 0:
            return ExpertResult(
                expert_id=self.expert_id,
                capability=self.capability,
                status=ExecutionStatus.DEGRADED,
                prediction="SENSOR_GLITCH_SUSPECTED",
                confidence=0.0,
                evidence=[],
                timestamp_ns=now_ns,
                provenance=ModelProvenance(
                    runtime="deterministic-kinetic",
                    model_name="VectorMagnitudeAnalyzer",
                    version="1.0.0",
                    device="cpu"
                ),
                limitations=[glitch_reason or "All accelerometer samples rejected during validation"],
                latency_ms=(time.perf_counter() - start_t) * 1000.0
            )

        # Gravitational constant ~9.81 m/s² (1.0g)
        # Normal walking: ~9.5 - 14.5 m/s²
        # High impact / kinetic jerk: >= 24.5 m/s² (~2.5g)
        # Severe fall or collision: >= 30.0 m/s²
        prediction = "NORMAL_MOTION"
        confidence = 0.85

        if max_magnitude >= 24.5:
            confidence = min(0.99, 0.70 + (max_magnitude - 24.5) / 30.0)
            if max_magnitude >= 30.0:
                prediction = "PEDESTRIAN_FALL_OR_IMPACT"
                evidence_type = EvidenceType.PEDESTRIAN_FALL
            else:
                prediction = "HIGH_KINETIC_JERK"
                evidence_type = EvidenceType.KINETIC_JERK

            evidence_list.append({
                "evidence_id": f"motion_{now_ns}",
                "expert_id": self.expert_id,
                "evidence_type": evidence_type.value,
                "confidence": confidence,
                "timestamp_ns": now_ns,
                "source_sensor": SensorType.ACCELEROMETER.value,
                "attributes": {
                    "peak_magnitude_mps2": round(max_magnitude, 2),
                    "g_force": round(max_magnitude / 9.80665, 2),
                    "valid_samples": valid_sample_count,
                    "glitch_detected": has_glitch
                },
                "weight": 1.5
            })

        limitations = ["Assumes sensor calibration aligned with Earth gravity"]
        if has_glitch:
            limitations.append(glitch_reason or "Degraded sensor samples detected")

        return ExpertResult(
            expert_id=self.expert_id,
            capability=self.capability,
            status=ExecutionStatus.DEGRADED if has_glitch else ExecutionStatus.SUCCESS,
            prediction=prediction,
            confidence=confidence,
            evidence=evidence_list,
            timestamp_ns=now_ns,
            provenance=ModelProvenance(
                runtime="deterministic-kinetic",
                model_name="VectorMagnitudeAnalyzer",
                version="1.0.0",
                device="cpu"
            ),
            limitations=limitations,
            latency_ms=(time.perf_counter() - start_t) * 1000.0
        )
