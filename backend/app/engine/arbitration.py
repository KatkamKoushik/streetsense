from typing import List, Tuple
from app.schemas.experts import ExpertResult, ExecutionStatus, ExpertCapability
from app.schemas.evidence import EvidenceItem, EvidenceType


class ArbitrationEngine:
    """
    Conflict Arbitration Engine.
    Examines concurrent expert predictions and underlying evidence.
    Detects contradictions (e.g. motion detector claims impact but sensor quality claims bad data;
    or vision claims clear road but motion claims collision).
    Calculates cross-expert agreement and signals whether escalation is required.
    """

    def arbitrate(
        self,
        results: List[ExpertResult],
        evidence_items: List[EvidenceItem]
    ) -> Tuple[float, List[str], bool]:
        """
        Returns:
            agreement_score: float (0.0 to 1.0)
            conflicts: List[str] describing contradictions
            escalation_required: bool
        """
        if not results:
            return 1.0, [], False

        conflicts = []
        agreement_score = 1.0
        escalation_required = False

        # Check Sensor Quality vs High-Confidence Claims
        sq_result = next((r for r in results if r.capability == ExpertCapability.SENSOR_QUALITY), None)
        has_high_motion = any(
            e.evidence_type in (EvidenceType.KINETIC_JERK, EvidenceType.PEDESTRIAN_FALL)
            for e in evidence_items
        )

        if sq_result and sq_result.prediction == "DEGRADED" and has_high_motion:
            conflicts.append("High kinetic motion spike detected concurrently with degraded sensor quality/jitter.")
            agreement_score -= 0.35
            escalation_required = True

        # Check Motion vs Vision disagreement if both executed
        motion_result = next((r for r in results if r.capability == ExpertCapability.MOTION_ANALYSIS), None)
        vision_result = next((r for r in results if r.capability == ExpertCapability.OBJECT_DETECTION), None)

        if motion_result and vision_result:
            if motion_result.status == ExecutionStatus.SUCCESS and vision_result.status == ExecutionStatus.SUCCESS:
                if motion_result.prediction == "PEDESTRIAN_FALL_OR_IMPACT" and vision_result.prediction == "CLEAR_PATH":
                    conflicts.append("Motion indicates impact/fall while vision indicates unobstructed clear pathway.")
                    agreement_score -= 0.25
                    escalation_required = True

        agreement_score = max(0.1, min(1.0, agreement_score))
        return agreement_score, conflicts, escalation_required


arbitration_engine = ArbitrationEngine()
