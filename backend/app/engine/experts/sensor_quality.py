import time
from typing import Set
from app.engine.base import BaseExpert
from app.schemas.experts import (
    ExpertCapability, ExecutionStatus, ExpertRequest, ExpertResult, ModelProvenance
)
from app.schemas.sensors import SensorType, SensorAccuracy
from app.schemas.evidence import EvidenceType


class SensorQualityExpert(BaseExpert):
    def __init__(self):
        super().__init__(
            expert_id="sensor_quality_expert_v1",
            capability=ExpertCapability.SENSOR_QUALITY,
            required_sensors=set(),
            estimated_latency_ms=0.5,
            estimated_energy_cost="LOW"
        )

    def is_available(self) -> bool:
        return True

    async def execute(self, request: ExpertRequest) -> ExpertResult:
        start_t = time.perf_counter()
        now_ns = time.time_ns()

        if not request.sensor_snapshots:
            return ExpertResult(
                expert_id=self.expert_id,
                capability=self.capability,
                status=ExecutionStatus.DEGRADED,
                prediction="NO_SNAPSHOTS_PROVIDED",
                confidence=0.0,
                evidence=[],
                timestamp_ns=now_ns,
                provenance=ModelProvenance(
                    runtime="deterministic-heuristic",
                    model_name="SensorQualityExpert",
                    version="1.0.0",
                    device="cpu"
                ),
                limitations=["No sensor snapshots in request window"],
                latency_ms=(time.perf_counter() - start_t) * 1000.0
            )

        unreliable_count = sum(1 for s in request.sensor_snapshots if s.accuracy == SensorAccuracy.UNRELIABLE)
        total_count = len(request.sensor_snapshots)
        quality_score = max(0.0, 1.0 - (unreliable_count / total_count))

        evidence = [{
            "evidence_id": f"sq_{now_ns}",
            "expert_id": self.expert_id,
            "evidence_type": EvidenceType.SENSOR_QUALITY_CHECK.value,
            "confidence": quality_score,
            "timestamp_ns": now_ns,
            "source_sensor": "ALL_SENSORS",
            "attributes": {
                "total_snapshots": total_count,
                "unreliable_count": unreliable_count,
                "quality_ratio": quality_score
            },
            "weight": 1.0
        }]

        return ExpertResult(
            expert_id=self.expert_id,
            capability=self.capability,
            status=ExecutionStatus.SUCCESS,
            prediction="OPTIMAL" if quality_score > 0.8 else "DEGRADED",
            confidence=quality_score,
            evidence=evidence,
            timestamp_ns=now_ns,
            provenance=ModelProvenance(
                runtime="deterministic-heuristic",
                model_name="SensorQualityExpert",
                version="1.0.0",
                device="cpu"
            ),
            limitations=[],
            latency_ms=(time.perf_counter() - start_t) * 1000.0
        )
