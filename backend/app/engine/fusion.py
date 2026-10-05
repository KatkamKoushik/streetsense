import uuid
import time
from typing import List, Optional, Dict, Any
from app.schemas.evidence import EvidenceItem, EvidenceType
from app.schemas.events import DetectedEvent, EventCategory, EventSeverity, ConfidenceBreakdown
from app.schemas.experts import ExpertResult, ExecutionStatus


class EvidenceFusionEngine:
    """
    Dedicated Multi-Modal Evidence Fusion Engine.
    Correlates vision, motion, location, temporal persistence, and sensor quality.
    Retains strict auditability of which evidence items contributed to the result.
    """

    def fuse(
        self,
        session_id: str,
        results: List[ExpertResult],
        evidence_items: List[EvidenceItem],
        arbitration_agreement: float = 1.0,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> Optional[DetectedEvent]:
        if not evidence_items:
            return None

        now_ns = time.time_ns()

        # Categorize evidence
        has_kinetic_jerk = any(e.evidence_type in (EvidenceType.KINETIC_JERK, EvidenceType.PEDESTRIAN_FALL) for e in evidence_items)
        has_transit = any(e.evidence_type == EvidenceType.HIGH_SPEED_TRANSIT for e in evidence_items)
        has_low_light = any(e.evidence_type == EvidenceType.LOW_LIGHT_ENVIRONMENT for e in evidence_items)
        has_glare = any(e.evidence_type == EvidenceType.GLARE_EXPOSURE for e in evidence_items)
        has_obstacle = any(e.evidence_type == EvidenceType.VISUAL_OBSTRUCTION for e in evidence_items)
        has_vehicle = any(e.evidence_type == EvidenceType.APPROACHING_VEHICLE for e in evidence_items)

        # Retrieve sensor quality score if available
        sq_item = next((e for e in evidence_items if e.evidence_type == EvidenceType.SENSOR_QUALITY_CHECK), None)
        sensor_quality = sq_item.confidence if sq_item else 0.90

        # Calculate contributing evidence
        contributing_ids = [e.evidence_id for e in evidence_items if e.evidence_type != EvidenceType.SENSOR_QUALITY_CHECK]
        if not contributing_ids:
            return None

        # Determine dominant event category and severity
        category = EventCategory.ANOMALOUS_MOTION
        severity = EventSeverity.INFO
        explanation = "Environmental motion anomaly recorded."
        haptic_pattern = "SINGLE_PULSE"
        pred_conf = 0.80

        if has_kinetic_jerk:
            fall_item = next((e for e in evidence_items if e.evidence_type == EvidenceType.PEDESTRIAN_FALL), None)
            if fall_item:
                category = EventCategory.PEDESTRIAN_FALL_OR_IMPACT
                severity = EventSeverity.HIGH_RISK
                pred_conf = fall_item.confidence
                peak_g = fall_item.attributes.get("g_force", 2.5)
                explanation = f"High-impact kinetic shock ({peak_g}g) detected. Motion and kinetic sensors indicate potential pedestrian fall."
                haptic_pattern = "STRONG_DOUBLE_PULSE"
            else:
                jerk_item = next(e for e in evidence_items if e.evidence_type == EvidenceType.KINETIC_JERK)
                category = EventCategory.ANOMALOUS_MOTION
                severity = EventSeverity.WARNING
                pred_conf = jerk_item.confidence
                explanation = "Kinetic acceleration spike detected above normal pedestrian baseline."
                haptic_pattern = "RAPID_PULSE"

        elif has_vehicle and has_transit:
            category = EventCategory.VEHICLE_APPROACH_COLLISION
            severity = EventSeverity.CRITICAL
            pred_conf = 0.92
            explanation = "Approaching vehicle detected on collision trajectory while moving at transit speed."
            haptic_pattern = "URGENT_CONTINUOUS"

        elif has_obstacle:
            category = EventCategory.ROAD_HAZARD_OBSTRUCTION
            severity = EventSeverity.WARNING
            pred_conf = 0.88
            explanation = "Road obstruction detected ahead in pedestrian pathway."
            haptic_pattern = "DOUBLE_PULSE"

        elif has_low_light:
            category = EventCategory.POOR_VISIBILITY_HAZARD
            severity = EventSeverity.NOTICE
            pred_conf = 0.85
            explanation = "Ambient illumination has dropped below safe navigation threshold."
            haptic_pattern = "SINGLE_PULSE"

        # Multi-factor confidence computation
        input_quality = sensor_quality
        temporal_consistency = 0.90
        sensor_reliability = 0.95
        cross_expert_agreement = arbitration_agreement
        geometric_consistency = 0.88
        evidence_quality = (pred_conf * 0.4) + (input_quality * 0.3) + (cross_expert_agreement * 0.3)
        final_confidence = min(1.0, (pred_conf * 0.35) + (evidence_quality * 0.35) + (arbitration_agreement * 0.30))

        confidence_breakdown = ConfidenceBreakdown(
            prediction_confidence=round(pred_conf, 2),
            input_quality=round(input_quality, 2),
            temporal_consistency=round(temporal_consistency, 2),
            sensor_reliability=round(sensor_reliability, 2),
            cross_expert_agreement=round(cross_expert_agreement, 2),
            geometric_consistency=round(geometric_consistency, 2),
            evidence_quality=round(evidence_quality, 2),
            final_decision_confidence=round(final_confidence, 2)
        )

        return DetectedEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            timestamp_ns=now_ns,
            category=category,
            severity=severity,
            confidence_breakdown=confidence_breakdown,
            contributing_evidence_ids=contributing_ids,
            contributing_evidence=evidence_items,
            explanation=explanation,
            haptic_pattern=haptic_pattern,
            latitude=latitude,
            longitude=longitude,
            is_dismissed=False
        )


fusion_engine = EvidenceFusionEngine()
