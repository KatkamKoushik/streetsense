import time
from typing import Set
from app.engine.base import BaseExpert
from app.schemas.experts import (
    ExpertCapability, ExecutionStatus, ExpertRequest, ExpertResult, ModelProvenance
)
from app.schemas.sensors import SensorType
from app.schemas.evidence import EvidenceType


class LocationExpert(BaseExpert):
    def __init__(self):
        super().__init__(
            expert_id="location_expert_v1",
            capability=ExpertCapability.LOCATION_ANALYSIS,
            required_sensors={SensorType.GPS},
            estimated_latency_ms=0.8,
            estimated_energy_cost="LOW"
        )

    def is_available(self) -> bool:
        return True

    async def execute(self, request: ExpertRequest) -> ExpertResult:
        start_t = time.perf_counter()
        now_ns = time.time_ns()

        loc = request.location_snapshot
        if not loc or not loc.is_available or loc.accuracy_meters is None or loc.accuracy_meters >= 900.0:
            sentinel_val = loc.accuracy_meters if loc else None
            return self.create_fallback_result(
                ExecutionStatus.UNAVAILABLE,
                f"GPS fix unavailable or accuracy degraded (sentinel: {sentinel_val}m)"
            )

        # Stale GPS fix rejection (75-N001): Reject fixes older than 10 seconds
        if loc.timestamp_ns > 0:
            age_seconds = (now_ns - loc.timestamp_ns) / 1e9
            if age_seconds > 10.0:
                return self.create_fallback_result(
                    ExecutionStatus.UNAVAILABLE,
                    f"GPS fix rejected: stale location fix ({age_seconds:.1f}s old > 10.0s threshold)"
                )

        evidence_list = []
        prediction = "STATIONARY"
        confidence = 0.90

        # Accuracy assessment
        if loc.accuracy_meters > 25.0:
            confidence = max(0.40, 1.0 - (loc.accuracy_meters / 100.0))

        speed = loc.speed_mps or 0.0

        if speed > 6.0:  # ~21.6 km/h
            prediction = "HIGH_SPEED_TRANSIT"
            evidence_list.append({
                "evidence_id": f"loc_{now_ns}",
                "expert_id": self.expert_id,
                "evidence_type": EvidenceType.HIGH_SPEED_TRANSIT.value,
                "confidence": confidence,
                "timestamp_ns": now_ns,
                "source_sensor": SensorType.GPS.value,
                "attributes": {
                    "speed_mps": speed,
                    "speed_kmh": round(speed * 3.6, 1),
                    "accuracy_meters": loc.accuracy_meters,
                    "latitude": loc.latitude,
                    "longitude": loc.longitude
                },
                "weight": 1.2
            })
        elif speed > 0.8:
            prediction = "PEDESTRIAN_WALKING"
        else:
            prediction = "STATIONARY"

        return ExpertResult(
            expert_id=self.expert_id,
            capability=self.capability,
            status=ExecutionStatus.SUCCESS,
            prediction=prediction,
            confidence=confidence,
            evidence=evidence_list,
            timestamp_ns=now_ns,
            provenance=ModelProvenance(
                runtime="deterministic-geospatial",
                model_name="KinematicLocationAnalyzer",
                version="1.0.0",
                device="cpu"
            ),
            limitations=["Indoor GPS multipath signals may degrade accuracy"],
            latency_ms=(time.perf_counter() - start_t) * 1000.0
        )
