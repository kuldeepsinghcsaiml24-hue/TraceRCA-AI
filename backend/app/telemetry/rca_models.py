from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


CONFIDENCE_DIMENSIONS = (
    "direct_fault_evidence",
    "temporal_relevance",
    "topology_relevance",
    "cross_source_corroboration",
    "evidence_coverage",
    "evidence_consistency",
)


class EvidenceConfidenceAssessment(BaseModel):
    """Evidence-strength assessment, not a probability of causation."""

    confidence_score: float = Field(ge=0, le=100)
    confidence_level: Literal["LOW", "MODERATE", "HIGH"]
    evidence_quality: dict[str, float | None]
    confidence_limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assessment(self):
        """Validate dimensions, finite scores, and confidence consistency."""
        import math

        if set(self.evidence_quality) != set(CONFIDENCE_DIMENSIONS):
            raise ValueError(
                "evidence_quality must contain exactly the six "
                "defined confidence dimensions"
            )

        for dimension, score in self.evidence_quality.items():
            if score is not None:
                if not math.isfinite(score) or not 0 <= score <= 100:
                    raise ValueError(
                        f"Dimension '{dimension}' must be None or a "
                        "finite score from 0 to 100"
                    )

        if not math.isfinite(self.confidence_score):
            raise ValueError("confidence_score must be finite")

        if self.confidence_score < 40:
            allowed_levels = {"LOW"}
        elif self.confidence_score < 70:
            allowed_levels = {"MODERATE"}
        else:
            # HIGH safeguards may cap a score of 70+ at MODERATE.
            allowed_levels = {"MODERATE", "HIGH"}

        if self.confidence_level not in allowed_levels:
            raise ValueError(
                "confidence_level is inconsistent with the numerical "
                "score and HIGH-confidence eligibility rules"
            )

        if any(not item.strip() for item in self.confidence_limitations):
            raise ValueError(
                "confidence_limitations cannot contain empty strings"
            )

        return self

VerificationStatus = Literal[
    "HYPOTHESIS",
    "VERIFIED",
    "REJECTED",
]


class RCACandidate(BaseModel):
    """An evidence-backed hypothesis for an incident root cause."""

    candidate_id: UUID = Field(default_factory=uuid4)

    service_name: str = Field(min_length=1, max_length=255)
    hypothesis: str = Field(min_length=1, max_length=2000)

    ranking_score: float = Field(ge=0, le=100)

    score_breakdown: dict[str, float] = Field(default_factory=dict)

    supporting_evidence_ids: list[int | UUID] = Field(
        default_factory=list
    )
    contradictory_evidence_ids: list[int | UUID] = Field(
        default_factory=list
    )

    limitations: list[str] = Field(default_factory=list)

    confidence_assessment: EvidenceConfidenceAssessment | None = None

    verification_status: VerificationStatus = "HYPOTHESIS"

    @model_validator(mode="after")
    def validate_score_breakdown(self):
        """Require finite, non-negative component scores."""
        import math

        for component, score in self.score_breakdown.items():
            if not math.isfinite(score) or score < 0:
                raise ValueError(
                    f"Score component '{component}' must be finite "
                    "and non-negative"
                )

        return self


class RCAResult(BaseModel):
    """Structured outcome of a root-cause investigation."""

    incident_id: UUID

    evidence_status: Literal["AVAILABLE", "PARTIAL", "NONE"]

    candidates: list[RCACandidate] = Field(default_factory=list)

    investigation_status: Literal[
        "CANDIDATES_FOUND",
        "INSUFFICIENT_EVIDENCE",
        "NO_CANDIDATES",
    ]

    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_investigation_status(self):
        """Keep the summary status consistent with available candidates."""
        if self.investigation_status == "CANDIDATES_FOUND":
            if not self.candidates:
                raise ValueError(
                    "CANDIDATES_FOUND requires at least one candidate"
                )

        if self.investigation_status == "NO_CANDIDATES":
            if self.candidates:
                raise ValueError(
                    "NO_CANDIDATES cannot contain candidates"
                )

        if self.investigation_status == "INSUFFICIENT_EVIDENCE":
            if self.evidence_status == "NONE" and self.candidates:
                raise ValueError(
                    "Candidates cannot be reported when evidence status is NONE"
                )

        return self


