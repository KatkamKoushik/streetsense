from typing import List
from app.schemas.events import DetectedEvent
from app.schemas.evidence import EvidenceItem


class LocalReasoningExpert:
    """
    Local Reasoning Expert.
    Synthesizes structured evidence into grounded, human-readable explanations.
    Strictly forbidden from hallucinating or inventing uncited claims.
    """

    def generate_explanation(self, event: DetectedEvent, evidence_items: List[EvidenceItem]) -> str:
        if not evidence_items:
            return "No concrete sensor evidence available to explain this event."

        cited_evidence_types = list(set([e.evidence_type.value for e in evidence_items]))
        sources = list(set([e.source_sensor for e in evidence_items]))

        return (
            f"Alert: {event.category.value} [{event.severity.value}]. "
            f"Reasoning: {event.explanation} "
            f"Corroborating Evidence: [{', '.join(cited_evidence_types)}] "
            f"across sensor sources: [{', '.join(sources)}]. "
            f"Calculated agreement confidence: {event.confidence_breakdown.cross_expert_agreement}."
        )


reasoning_expert = LocalReasoningExpert()
