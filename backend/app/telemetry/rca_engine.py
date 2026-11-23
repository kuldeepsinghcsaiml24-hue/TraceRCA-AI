"""Heuristic root-cause candidate generation and ranking for TraceRCA."""

from __future__ import annotations

from typing import Any

from backend.app.telemetry.incident import IncidentEvidence
from backend.app.telemetry.evidence_confidence import assess_evidence_confidence
from backend.app.telemetry.rca_models import RCACandidate, RCAResult


WEIGHTS = {
    "trace_evidence": 0.10,
    "temporal_consistency": 0.10,
    "topology_relevance": 0.10,
    "log_evidence": 0.10,
    "metric_anomaly_evidence": 0.10,
    "dependency_failure_evidence": 0.50,
}

ERROR_TERMS = (
    "error",
    "failed",
    "failure",
    "exception",
    "timeout",
    "unavailable",
    "connection attempts failed",
    "connection refused",
)


def _event_key(event_id: Any) -> str:
    """Normalize evidence IDs for deterministic matching."""
    return str(event_id)


def _temporal_events(evidence: IncidentEvidence) -> dict[str, Any]:
    """Index temporal classifications by event ID."""
    if evidence.temporal_analysis is None:
        return {}

    return {
        _event_key(item.event_id): item
        for item in evidence.temporal_analysis.events
    }


def _topology_scores(evidence: IncidentEvidence) -> dict[str, float]:
    """Score dependency relevance without treating it as causal proof."""
    incident_service = evidence.incident.service_name
    scores = {incident_service: 50.0}

    for depth, service in enumerate(evidence.upstream_dependencies, start=1):
        if service and service != incident_service:
            scores[service] = max(scores.get(service, 0.0), 100.0 / depth)

    topology = evidence.topology
    if topology is not None:
        # An edge A -> B means A depends on B, so B is upstream of A.
        for edge in topology.dependencies:
            if edge.source_service == incident_service:
                scores[edge.target_service] = max(
                    scores.get(edge.target_service, 0.0), 100.0
                )

    return scores


def _dependency_failure_evidence(
    dependency_name: str,
    evidence: IncidentEvidence,
) -> list[Any]:
    """Find caller error logs that name a known upstream dependency."""
    topology = evidence.topology
    if topology is None:
        return []

    incident_service = evidence.incident.service_name

    known_dependencies = {
        edge.target_service.lower(): edge.target_service
        for edge in topology.dependencies
        if edge.source_service == incident_service
    }

    dependency = known_dependencies.get(dependency_name.lower())
    if dependency is None:
        return []

    def normalize(value: str) -> str:
        return value.lower().replace("-", " ").replace("_", " ").strip()

    dependency_names = {
        normalize(dependency),
        normalize(dependency).replace(" service", ""),
    }

    matches = []

    for event in evidence.telemetry_events:
        if (
            event.service_name != incident_service
            or event.event_type != "log"
        ):
            continue

        message = normalize(event.message or "")
        if not any(term in message for term in ERROR_TERMS):
            continue

        if any(name and name in message for name in dependency_names):
            matches.append(event)

    return matches


def _score_candidate(
    service_name: str,
    evidence: IncidentEvidence,
    temporal_by_id: dict[str, Any],
    topology_scores: dict[str, float],
) -> tuple[float, dict[str, float], list[Any], list[Any], list[str]]:
    """Compute an explainable 0-100 heuristic ranking score."""
    events = [
        event
        for event in evidence.telemetry_events
        if event.service_name == service_name
    ]

    traces = [e for e in events if e.event_type == "trace"]
    logs = [e for e in events if e.event_type == "log"]
    metrics = [e for e in events if e.event_type == "metric"]

    supporting_ids: dict[str, Any] = {}
    contradictory_ids: dict[str, Any] = {}
    limitations: list[str] = []

    def support(event_id: Any) -> None:
        supporting_ids[_event_key(event_id)] = event_id

    def contradict(event_id: Any) -> None:
        contradictory_ids[_event_key(event_id)] = event_id

    # Explicit trace errors are stronger than the mere presence of a trace.
    trace_score = 0.0
    for event in traces:
        if (event.status or "").upper() == "ERROR":
            trace_score = 100.0
            support(event.event_id)

    # Direct error logs from the candidate service.
    log_score = 0.0
    for event in logs:
        message = (event.message or "").lower()
        if any(term in message for term in ERROR_TERMS):
            log_score = 100.0
            support(event.event_id)

    # Indirect evidence: the incident service reports a failure involving
    # this known upstream dependency.
    implicated_logs = _dependency_failure_evidence(service_name, evidence)
    if implicated_logs:
        log_score = max(log_score, 70.0)
        for event in implicated_logs:
            support(event.event_id)
        limitations.append(
            "Dependency failure is inferred from the caller's error log; "
            "the dependency did not necessarily emit direct fault telemetry."
        )

    anomaly = evidence.incident.anomaly
    metric_score = 0.0

    if anomaly is not None and anomaly.service_name == service_name:
        metric_score = {
            "LOW": 40.0,
            "MEDIUM": 70.0,
            "HIGH": 100.0,
        }.get(anomaly.severity, 0.0)

    # Temporal precedence strengthens explicit fault signals, but timing alone
    # is deliberately capped at a weak score.
    temporal_score = 0.0
    for event in events:
        temporal = temporal_by_id.get(_event_key(event.event_id))
        if temporal is None or temporal.position != "BEFORE":
            continue

        temporal_score = max(temporal_score, 40.0)
        is_error = (
            (event.status or "").upper() == "ERROR"
            or (
                event.event_type == "log"
                and any(
                    term in (event.message or "").lower()
                    for term in ERROR_TERMS
                )
            )
        )
        if is_error:
            temporal_score = 100.0
            support(event.event_id)

    topology_score = topology_scores.get(service_name, 0.0)

    if not traces:
        limitations.append("No trace events were available for this service.")
    if not logs and not implicated_logs:
        limitations.append("No log events were available for this service.")
    if not metrics and not (
        anomaly is not None and anomaly.service_name == service_name
    ):
        limitations.append("No service-specific metric evidence was available.")
    if evidence.temporal_analysis is None:
        limitations.append("Temporal analysis was unavailable.")
    if evidence.topology is None:
        limitations.append("Topology was unavailable.")

    dependency_failure_score = 100.0 if implicated_logs else 0.0

    breakdown = {
        "trace_evidence": trace_score,
        "temporal_consistency": temporal_score,
        "topology_relevance": topology_score,
        "log_evidence": log_score,
        "metric_anomaly_evidence": metric_score,
        "dependency_failure_evidence": dependency_failure_score,
    }

    weighted_score = sum(
        breakdown[name] * weight for name, weight in WEIGHTS.items()
    )

    breakdown["contradiction_penalty"] = 0.0
    breakdown["weighted_base_score"] = round(weighted_score, 2)

    score = round(max(0.0, min(100.0, weighted_score)), 2)

    return (
        score,
        breakdown,
        list(supporting_ids.values()),
        list(contradictory_ids.values()),
        sorted(set(limitations)),
    )


def rank_root_causes(evidence: IncidentEvidence) -> RCAResult:
    """Rank candidate services using available incident evidence.

    Scores are diagnostic heuristics, not probabilities or proof of causation.
    """
    general_limitations = [
        "Ranking scores are heuristic diagnostic scores, not probabilities.",
        "Temporal precedence and topology do not independently prove causation.",
        "Initial weights require validation against controlled fault scenarios.",
    ]

    if evidence.evidence_status == "NONE" or not evidence.telemetry_events:
        return RCAResult(
            incident_id=evidence.incident.incident_id,
            evidence_status=evidence.evidence_status,
            candidates=[],
            investigation_status="INSUFFICIENT_EVIDENCE",
            limitations=general_limitations + [
                "No telemetry evidence was available to rank root-cause candidates."
            ],
        )

    temporal_by_id = _temporal_events(evidence)
    topology_scores = _topology_scores(evidence)

    candidate_services = {
        evidence.incident.service_name,
        *evidence.upstream_dependencies,
    }
    candidate_services.update(
        event.service_name
        for event in evidence.telemetry_events
        if event.service_name.strip()
    )

    candidates: list[RCACandidate] = []

    for service_name in sorted(candidate_services):
        if not service_name or not service_name.strip():
            continue

        events = [
            event
            for event in evidence.telemetry_events
            if event.service_name == service_name
        ]

        anomaly = evidence.incident.anomaly
        has_explicit_fault = any(
            (event.status or "").upper() == "ERROR"
            or (
                event.event_type == "log"
                and any(
                    term in (event.message or "").lower()
                    for term in ERROR_TERMS
                )
            )
            for event in events
        )
        has_service_anomaly = (
            anomaly is not None and anomaly.service_name == service_name
        )
        implicated_logs = _dependency_failure_evidence(
            service_name,
            evidence,
        )

        # A topology edge alone is not sufficient to manufacture a candidate.
        if (
            not has_explicit_fault
            and not has_service_anomaly
            and not implicated_logs
        ):
            continue

        (
            score,
            breakdown,
            supporting_ids,
            contradictory_ids,
            candidate_limitations,
        ) = _score_candidate(
            service_name,
            evidence,
            temporal_by_id,
            topology_scores,
        )

        candidates.append(
            RCACandidate(
                service_name=service_name,
                hypothesis=(
                    f"{service_name} is a plausible root-cause candidate for "
                    f"the incident affecting {evidence.incident.service_name}. "
                    "This hypothesis requires further verification."
                ),
                ranking_score=score,
                score_breakdown=breakdown,
                supporting_evidence_ids=supporting_ids,
                contradictory_evidence_ids=contradictory_ids,
                limitations=candidate_limitations,
                verification_status="HYPOTHESIS",
            )
        )

    # D2.6 assesses evidence quality without changing D2.5 ranking.
    for candidate in candidates:
        candidate.confidence_assessment = assess_evidence_confidence(
            evidence,
            candidate,
        )

    candidates.sort(
        key=lambda candidate: (
            -candidate.ranking_score,
            candidate.service_name,
        )
    )

    if not candidates:
        return RCAResult(
            incident_id=evidence.incident.incident_id,
            evidence_status=evidence.evidence_status,
            candidates=[],
            investigation_status="INSUFFICIENT_EVIDENCE",
            limitations=general_limitations + [
                "No service had explicit fault-related evidence sufficient "
                "to generate a candidate."
            ],
        )

    return RCAResult(
        incident_id=evidence.incident.incident_id,
        evidence_status=evidence.evidence_status,
        candidates=candidates,
        investigation_status="CANDIDATES_FOUND",
        limitations=general_limitations,
    )


