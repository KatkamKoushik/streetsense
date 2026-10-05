import abc
import time
from typing import List, Set, Dict, Any, Optional
from app.schemas.experts import (
    ExpertCapability, ExecutionStatus, ExpertRequest, ExpertResult, ModelProvenance
)
from app.schemas.sensors import SensorType


class BaseExpert(abc.ABC):
    def __init__(
        self,
        expert_id: str,
        capability: ExpertCapability,
        required_sensors: Set[SensorType],
        estimated_latency_ms: float,
        estimated_energy_cost: str = "LOW"  # LOW, MEDIUM, HIGH
    ):
        self.expert_id = expert_id
        self.capability = capability
        self.required_sensors = required_sensors
        self.estimated_latency_ms = estimated_latency_ms
        self.estimated_energy_cost = estimated_energy_cost

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Checks if required models, hardware sensors, or libraries are ready."""
        pass

    @abc.abstractmethod
    async def execute(self, request: ExpertRequest) -> ExpertResult:
        """Performs expert evaluation and returns structured evidence and confidence."""
        pass

    def create_fallback_result(self, status: ExecutionStatus, limitation: str) -> ExpertResult:
        return ExpertResult(
            expert_id=self.expert_id,
            capability=self.capability,
            status=status,
            prediction=None,
            confidence=0.0,
            evidence=[],
            timestamp_ns=time.time_ns(),
            provenance=ModelProvenance(
                runtime="deterministic-fallback",
                model_name=self.expert_id,
                version="1.0.0",
                device="cpu"
            ),
            limitations=[limitation],
            latency_ms=0.0
        )
