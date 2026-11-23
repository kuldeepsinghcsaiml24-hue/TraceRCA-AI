from sqlalchemy.ext.asyncio import AsyncSession

from .incident import IncidentContext
from .incident_evidence_service import build_incident_evidence
from .rca_api_schemas import RCAAnalysisResponse
from .rca_engine import rank_root_causes
from .rca_explainer import explain_root_causes


RCA_DISCLAIMER = (
    "Rankings are heuristic hypotheses, not calibrated "
    "probabilities or proof of causation."
)


async def execute_rca_analysis(
    db: AsyncSession,
    incident: IncidentContext,
) -> RCAAnalysisResponse:
    """Execute the existing RCA pipeline and validate its public response."""
    evidence = await build_incident_evidence(
        db=db,
        incident=incident,
    )
    analysis = rank_root_causes(evidence)
    explanations = explain_root_causes(evidence, analysis)

    return RCAAnalysisResponse(
        incident_id=incident.incident_id,
        evidence=evidence,
        root_cause_analysis=analysis,
        explanations=explanations,
        disclaimer=RCA_DISCLAIMER,
    )
