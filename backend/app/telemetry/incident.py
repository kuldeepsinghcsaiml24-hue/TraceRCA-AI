from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from .anomaly import Anomaly
from .correlation import CorrelationResult
from .normalized import NormalizedTelemetry
from .topology import TopologyResponse
from .temporal_analysis import TemporalAnalysisResult


class IncidentContext(BaseModel):
    """Describe the incident being investigated."""

    incident_id: UUID = Field(default_factory=uuid4)

    service_name: str = Field(min_length=1, max_length=255)

    start_time: datetime
    end_time: datetime

    anomaly: Anomaly | None = None

    @model_validator(mode="after")
    def validate_incident_window(self):
        """Require a valid, timezone-aware investigation window."""
        if not self.service_name.strip():
            raise ValueError("service_name cannot be empty or whitespace")

        if (
            self.start_time.tzinfo is None
            or self.start_time.utcoffset() is None
            or self.end_time.tzinfo is None
            or self.end_time.utcoffset() is None
        ):
            raise ValueError(
                "start_time and end_time must be timezone-aware"
            )

        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")

        return self


class IncidentEvidence(BaseModel):
    """Collect the evidence associated with an incident."""

    incident: IncidentContext

    telemetry_events: list[NormalizedTelemetry] = Field(
        default_factory=list
    )

    correlations: list[CorrelationResult] = Field(
        default_factory=list
    )

    temporal_analysis: TemporalAnalysisResult | None = None
    topology: TopologyResponse | None = None

    upstream_dependencies: list[str] = Field(default_factory=list)

    downstream_impact: list[str] = Field(default_factory=list)

    evidence_status: Literal[
        "AVAILABLE",
        "PARTIAL",
        "NONE",
    ] = "NONE"

    unavailable_sources: list[Literal["telemetry", "topology"]] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def determine_evidence_status(self):
        """Derive completeness from telemetry and source retrieval failures."""
        if self.unavailable_sources:
            self.evidence_status = "PARTIAL"
        elif self.telemetry_events:
            self.evidence_status = "AVAILABLE"
        else:
            self.evidence_status = "NONE"

        return self




