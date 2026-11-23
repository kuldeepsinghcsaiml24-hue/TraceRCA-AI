"""Evidence-grounded explanations for TraceRCA root-cause candidates."""

from typing import Any

from backend.app.telemetry.graph_retrieval import retrieve_candidate_graph_evidence
from backend.app.telemetry.incident import IncidentEvidence
from backend.app.telemetry.rca_models import RCACandidate, RCAResult


def _interpret_graph_evidence(graph_evidence: dict[str, Any]) -> str:
    """Explain graph retrieval results without asserting causation."""
    status = graph_evidence["status"]
    incident = graph_evidence["incident_service"]
    candidate = graph_evidence["candidate_service"]
    relationship = graph_evidence["relationship"]

    if status == "TOPOLOGY_UNAVAILABLE":
        return (
            "Topology was unavailable, so the relationship between "
            f"{candidate} and {incident} could not be checked."
        )

    if status == "SERVICE_NOT_IN_TOPOLOGY":
        return (
            "The candidate or incident service was absent from the "
            "retrieved topology, so no graph relationship can be confirmed."
        )

    if status == "NO_PATH_FOUND":
        return (
            "No path was found between the candidate and incident services "
            "within the retrieved topology and depth limit. This does not "
            "prove that no relationship exists outside the retrieved graph."
        )

    if relationship == "INCIDENT_SERVICE":
        return (
            "The candidate is the incident service itself. This identifies "
            "the service under investigation but does not establish causation."
        )

    path = graph_evidence["path_services"]
    path_text = " -> ".join(path)
    edge_count = len(graph_evidence["path_edges"])
    path_kind = "direct" if edge_count == 1 else "indirect"

    return (
        f"The retrieved topology shows a {path_kind} structural connection "
        f"between candidate {candidate} and incident service {incident}: "
        f"{path_text}. The returned edges preserve their actual dependency "
        "directions. This relationship is contextual evidence, not proof "
        "that the candidate caused the incident."
    )


def _event_key(event_id: Any) -> str:
    """Normalize event identifiers for safe evidence matching."""
    return str(event_id)


def _event_summary(event: Any) -> dict[str, Any]:
    """Expose factual fields from a retrieved telemetry event."""
    return {
        "evidence_id": event.event_id,
        "event_type": event.event_type,
        "service_name": event.service_name,
        "timestamp": event.timestamp.isoformat(),
        "operation_name": event.operation_name,
        "status": event.status,
        "message": event.message,
        "metric_name": event.metric_name,
        "metric_value": event.metric_value,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
        "parent_span_id": event.parent_span_id,
    }


def _explain_candidate(
    evidence: IncidentEvidence,
    candidate: RCACandidate,
) -> dict[str, Any]:
    """Build a deterministic explanation from retrieved evidence and RCA output."""
    events_by_id = {
        _event_key(event.event_id): event
        for event in evidence.telemetry_events
    }

    supporting = []
    unresolved_supporting_ids = []

    for evidence_id in candidate.supporting_evidence_ids:
        event = events_by_id.get(_event_key(evidence_id))
        if event is None:
            unresolved_supporting_ids.append(str(evidence_id))
        else:
            supporting.append(_event_summary(event))

    contradictory = []
    unresolved_contradictory_ids = []

    for evidence_id in candidate.contradictory_evidence_ids:
        event = events_by_id.get(_event_key(evidence_id))
        if event is None:
            unresolved_contradictory_ids.append(str(evidence_id))
        else:
            contradictory.append(_event_summary(event))

    breakdown = candidate.score_breakdown
    reasons = []

    score_labels = {
        "trace_evidence": "trace error evidence",
        "temporal_consistency": "temporal consistency",
        "topology_relevance": "dependency topology relevance",
        "log_evidence": "log evidence",
        "metric_anomaly_evidence": "metric anomaly evidence",
        "dependency_failure_evidence": "dependency failure evidence",
    }

    for component, label in score_labels.items():
        score = breakdown.get(component, 0.0)
        if score > 0:
            reasons.append(
                {
                    "factor": component,
                    "label": label,
                    "component_score": score,
                }
            )

    temporal_positions = []
    if evidence.temporal_analysis is not None:
        temporal_by_id = {
            _event_key(item.event_id): item
            for item in evidence.temporal_analysis.events
        }
        for item in supporting:
            temporal = temporal_by_id.get(
                _event_key(item["evidence_id"])
            )
            if temporal is not None:
                temporal_positions.append(
                    {
                        "evidence_id": item["evidence_id"],
                        "position": temporal.position,
                        "seconds_from_anomaly": temporal.seconds_from_anomaly,
                    }
                )

    limitations = list(candidate.limitations)
    limitations.extend(candidate.confidence_assessment.confidence_limitations
                       if candidate.confidence_assessment is not None else [])

    if unresolved_supporting_ids:
        limitations.append(
            "Some supporting evidence IDs could not be resolved against "
            "the retrieved incident telemetry."
        )

    if unresolved_contradictory_ids:
        limitations.append(
            "Some contradictory evidence IDs could not be resolved against "
            "the retrieved incident telemetry."
        )

    if not supporting:
        limitations.append(
            "No candidate supporting evidence was resolved from the "
            "retrieved telemetry."
        )

    if candidate.service_name == evidence.incident.service_name:
        graph_relationship = "INCIDENT_SERVICE"
    elif candidate.service_name in evidence.upstream_dependencies:
        graph_relationship = "UPSTREAM_DEPENDENCY"
    elif candidate.service_name in evidence.downstream_impact:
        graph_relationship = "DOWNSTREAM_SERVICE"
    else:
        graph_relationship = "OTHER_OR_UNKNOWN"

    candidate_graph_evidence = retrieve_candidate_graph_evidence(
        topology=evidence.topology,
        incident_service=evidence.incident.service_name,
        candidate_service=candidate.service_name,
    )

    graph_context = {
        "incident_service": evidence.incident.service_name,
        "candidate_relationship": graph_relationship,
        "upstream_dependencies": list(evidence.upstream_dependencies),
        "downstream_impact": list(evidence.downstream_impact),
        "topology_available": evidence.topology is not None,
        "candidate_graph_evidence": candidate_graph_evidence,
        "interpretation": _interpret_graph_evidence(
            candidate_graph_evidence
        ),
    }

    if evidence.topology is None:
        limitations.append(
            "Topology data was unavailable; graph relationships could "
            "not be independently verified for this explanation."
        )

    return {
        "candidate_id": str(candidate.candidate_id),
        "service_name": candidate.service_name,
        "hypothesis": candidate.hypothesis,
        "verification_status": candidate.verification_status,
        "ranking_score": candidate.ranking_score,
        "score_breakdown": dict(candidate.score_breakdown),
        "ranking_reasons": reasons,
        "supporting_evidence": supporting,
        "contradictory_evidence": contradictory,
        "unresolved_supporting_evidence_ids": unresolved_supporting_ids,
        "unresolved_contradictory_evidence_ids": unresolved_contradictory_ids,
        "temporal_context": temporal_positions,
        "graph_context": graph_context,
        "upstream_dependencies": list(evidence.upstream_dependencies),
        "downstream_impact": list(evidence.downstream_impact),
        "confidence_assessment": (
            candidate.confidence_assessment.model_dump(mode="json")
            if candidate.confidence_assessment is not None
            else None
        ),
        "limitations": sorted(set(limitations)),
        "interpretation": (
            "This is an evidence-backed hypothesis, not proof of causation. "
            "Ranking scores are heuristic diagnostic scores, not probabilities."
        ),
    }


def explain_root_causes(
    evidence: IncidentEvidence,
    analysis: RCAResult,
) -> dict[str, Any]:
    """Explain ranked hypotheses without changing ranking or confidence."""
    if evidence.incident.incident_id != analysis.incident_id:
        raise ValueError(
            "Incident evidence and RCA analysis must have the same incident ID."
        )

    explanations = [
        _explain_candidate(evidence, candidate)
        for candidate in analysis.candidates
    ]

    return {
        "incident_id": str(analysis.incident_id),
        "evidence_status": analysis.evidence_status,
        "investigation_status": analysis.investigation_status,
        "candidate_explanations": explanations,
        "limitations": sorted(
            set(analysis.limitations)
            | {
                "Explanations are generated from retrieved evidence and "
                "heuristic RCA outputs; they do not establish causation."
            }
        ),
    }


