from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .incident import IncidentEvidence
from .rca_models import RCAResult


class RCAAnalysisResponse(BaseModel):
    """Validate the public response contract for RCA analysis."""

    incident_id: UUID
    evidence: IncidentEvidence
    root_cause_analysis: RCAResult
    explanations: dict[str, Any]
    disclaimer: str
