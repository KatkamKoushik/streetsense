import time
from typing import Set, List
from app.engine.base import BaseExpert
from app.schemas.experts import (
    ExpertCapability, ExecutionStatus, ExpertRequest, ExpertResult, ModelProvenance
)
from app.schemas.sensors import SensorType, SensorSnapshot
from app.schemas.evidence import EvidenceType


class IlluminationExpert(BaseExpert):
    def __init__(self):
        super().__init__(
            expert_id="illumination_expert_v1",
            capability=ExpertCapability.ILLUMINATION_ANALYSIS,
            required_sensors={SensorType.AMBIENT_LIGHT},
            estimated_latency_ms=0.4,
            estimated_energy_cost="LOW"
        )

    def is_available(self) -> bool:
        return True

    async def execute(self, request: ExpertRequest) -> ExpertResult:
        start_t = time.perf_counter()
        now_ns = time.time_ns()

        lux_snapshots: List[SensorSnapshot] = [
            s for s in request.sensor_snapshots if s.sensor_type == SensorType.AMBIENT_LIGHT
        ]

        if not lux_snapshots:
            return self.create_fallback_result(
                ExecutionStatus.UNAVAILABLE,
                "No ambient light snapshots provided in request"
            )

        latest_lux = lux_snapshots[-1].values[0] if lux_snapshots[-1].values else 100.0
        evidence_list = []
        prediction = "NORMAL_DAYLIGHT"
        confidence = 0.90

        if latest_lux < 10.0:
            prediction = "LOW_LIGHT_ENVIRONMENT"
            evidence_list.append({
                "evidence_id": f"ill_{now_ns}",
                "expert_id": self.expert_id,
                "evidence_type": EvidenceType.LOW_LIGHT_ENVIRONMENT.value,
                "confidence": 0.95 if latest_lux < 2.0 else 0.85,
                "timestamp_ns": now_ns,
                "source_sensor": SensorType.AMBIENT_LIGHT.value,
                "attributes": {
                    "lux_level": latest_lux,
                    "condition": "UNDER_ILLUMINATED"
                },
                "weight": 1.0
            })
        elif latest_lux > 15000.0:
            prediction = "GLARE_EXPOSURE"
            evidence_list.append({
                "evidence_id": f"ill_{now_ns}",
                "expert_id": self.expert_id,
                "evidence_type": EvidenceType.GLARE_EXPOSURE.value,
                "confidence": 0.90,
                "timestamp_ns": now_ns,
                "source_sensor": SensorType.AMBIENT_LIGHT.value,
                "attributes": {
                    "lux_level": latest_lux,
                    "condition": "DIRECT_GLARE"
                },
                "weight": 1.0
            })

        return ExpertResult(
            expert_id=self.expert_id,
            capability=self.capability,
            status=ExecutionStatus.SUCCESS,
            prediction=prediction,
            confidence=confidence,
            evidence=evidence_list,
            timestamp_ns=now_ns,
            provenance=ModelProvenance(
                runtime="deterministic-lux",
                model_name="AmbientPhotometricAnalyzer",
                version="1.0.0",
                device="cpu"
            ),
            limitations=["Does not account for device casing occlusion"],
            latency_ms=(time.perf_counter() - start_t) * 1000.0
        )
