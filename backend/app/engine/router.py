import logging
from typing import List, Tuple
from app.engine.registry import registry, ExpertRegistry
from app.engine.base import BaseExpert
from app.schemas.experts import ExpertCapability, ExpertRequest, ExpertResult
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.sensors import SensorType

logger = logging.getLogger("streetsense.router")


class SelectiveExpertRouter:
    """
    Selective Multi-Expert Router.
    Enforces the core rule: Do NOT run every model on every frame.
    Runs Level 0 (Sensor Quality) and Level 1 (Inexpensive IMU/Light/Location) first.
    Escalates to Level 2 (Vision) only if motion anomaly, ambiguity, or obstacle indicated.
    """

    def __init__(self, expert_registry: ExpertRegistry = registry):
        self.registry = expert_registry

    async def route_and_execute(self, request: ExpertRequest) -> Tuple[List[ExpertResult], List[EvidenceItem]]:
        results: List[ExpertResult] = []
        evidence_items: List[EvidenceItem] = []

        # Level 0: Sensor Quality Check
        sq_experts = self.registry.get_available_by_capability(ExpertCapability.SENSOR_QUALITY)
        if sq_experts:
            sq_res = await sq_experts[0].execute(request)
            results.append(sq_res)
            for ev in sq_res.evidence:
                evidence_items.append(EvidenceItem(**ev))

        # Level 1: Inexpensive Specialists
        # Motion
        if any(s.sensor_type == SensorType.ACCELEROMETER for s in request.sensor_snapshots):
            motion_experts = self.registry.get_available_by_capability(ExpertCapability.MOTION_ANALYSIS)
            if motion_experts:
                m_res = await motion_experts[0].execute(request)
                results.append(m_res)
                for ev in m_res.evidence:
                    evidence_items.append(EvidenceItem(**ev))

        # Location
        if request.location_snapshot:
            loc_experts = self.registry.get_available_by_capability(ExpertCapability.LOCATION_ANALYSIS)
            if loc_experts:
                l_res = await loc_experts[0].execute(request)
                results.append(l_res)
                for ev in l_res.evidence:
                    evidence_items.append(EvidenceItem(**ev))

        # Illumination
        if any(s.sensor_type == SensorType.AMBIENT_LIGHT for s in request.sensor_snapshots):
            ill_experts = self.registry.get_available_by_capability(ExpertCapability.ILLUMINATION_ANALYSIS)
            if ill_experts:
                i_res = await ill_experts[0].execute(request)
                results.append(i_res)
                for ev in i_res.evidence:
                    evidence_items.append(EvidenceItem(**ev))

        # Level 2: Escalation to Edge Vision Specialist
        # Only run vision if motion spike or explicit capability requested
        needs_vision = (
            ExpertCapability.OBJECT_DETECTION in request.target_capabilities or
            any(e.evidence_type in (EvidenceType.KINETIC_JERK, EvidenceType.PEDESTRIAN_FALL) for e in evidence_items)
        )

        if needs_vision:
            vision_experts = self.registry.get_available_by_capability(ExpertCapability.OBJECT_DETECTION)
            if vision_experts:
                v_res = await vision_experts[0].execute(request)
                results.append(v_res)
                for ev in v_res.evidence:
                    evidence_items.append(EvidenceItem(**ev))

        return results, evidence_items


router = SelectiveExpertRouter()
