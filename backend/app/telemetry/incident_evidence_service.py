from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.telemetry.correlation_service import correlate_events
from backend.app.telemetry.evidence_retrieval import retrieve_telemetry_events
from backend.app.telemetry.incident import IncidentContext, IncidentEvidence
from backend.app.telemetry.normalizers import normalize_event
from backend.app.telemetry.topology_analysis import (
    get_downstream_impact,
    get_upstream_dependencies,
)
from backend.app.telemetry.topology_service import topology_service
from backend.app.telemetry.temporal_analysis import analyze_temporal_events


async def build_incident_evidence(
    db: AsyncSession,
    incident: IncidentContext,
    limit: int = 500,
) -> IncidentEvidence:
    """
    Assemble bounded telemetry, event correlations, and service topology.

    Correlations describe relationships between observations; they do not
    establish that one event or service caused the incident.
    """
    unavailable_sources: list[str] = []
    normalized_events = []
    topology = None

    try:
        stored_events = await retrieve_telemetry_events(
            db=db,
            incident=incident,
            limit=limit,
        )
    except Exception:
        # Mark retrieval failure without hiding normalization errors.
        unavailable_sources.append("telemetry")
        stored_events = []

    # Keep normalization outside the retrieval exception handler.
    normalized_events = [
        normalize_event(event) for event in stored_events
    ]

    correlations = correlate_events(normalized_events)
    try:
        topology = await topology_service.get_incident_topology(
            incident.service_name
        )
    except Exception:
        # Topology is supplementary; its absence must be explicit.
        unavailable_sources.append("topology")

    upstream_dependencies = []
    downstream_impact = []

    if topology is not None:
        upstream_dependencies = get_upstream_dependencies(
            topology,
            incident.service_name,
        )
        downstream_impact = get_downstream_impact(
            topology,
            incident.service_name,
        )

    temporal_analysis = analyze_temporal_events(
        normalized_events,
        incident.anomaly,
        incident_service_name=incident.service_name,
        topology=topology,
        upstream_dependencies=upstream_dependencies,
        downstream_impact=downstream_impact,
    )

    return IncidentEvidence(
        incident=incident,
        telemetry_events=normalized_events,
        correlations=correlations,
        temporal_analysis=temporal_analysis,
        topology=topology,
        upstream_dependencies=upstream_dependencies,
        downstream_impact=downstream_impact,
        unavailable_sources=unavailable_sources,
    )




