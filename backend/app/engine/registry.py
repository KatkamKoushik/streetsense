from typing import Dict, List, Optional
from app.engine.base import BaseExpert
from app.schemas.experts import ExpertCapability


class ExpertRegistry:
    def __init__(self):
        self._experts_by_id: Dict[str, BaseExpert] = {}
        self._experts_by_capability: Dict[ExpertCapability, List[BaseExpert]] = {}

    def register(self, expert: BaseExpert) -> None:
        self._experts_by_id[expert.expert_id] = expert
        if expert.capability not in self._experts_by_capability:
            self._experts_by_capability[expert.capability] = []
        if expert not in self._experts_by_capability[expert.capability]:
            self._experts_by_capability[expert.capability].append(expert)

    def get_by_id(self, expert_id: str) -> Optional[BaseExpert]:
        return self._experts_by_id.get(expert_id)

    def get_by_capability(self, capability: ExpertCapability) -> List[BaseExpert]:
        return self._experts_by_capability.get(capability, [])

    def list_all(self) -> List[BaseExpert]:
        return list(self._experts_by_id.values())

    def get_available_by_capability(self, capability: ExpertCapability) -> List[BaseExpert]:
        return [e for e in self.get_by_capability(capability) if e.is_available()]


registry = ExpertRegistry()


def register_default_experts():
    from app.engine.experts.sensor_quality import SensorQualityExpert
    from app.engine.experts.motion import MotionExpert
    from app.engine.experts.location import LocationExpert
    from app.engine.experts.illumination import IlluminationExpert
    from app.engine.experts.vision_object import ObjectExpert

    registry.register(SensorQualityExpert())
    registry.register(MotionExpert())
    registry.register(LocationExpert())
    registry.register(IlluminationExpert())
    registry.register(ObjectExpert())


# Auto-register default specialists on module import
register_default_experts()
