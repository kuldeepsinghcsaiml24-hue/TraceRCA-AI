"""Evidence quality assessment for RCA candidates.

Scores describe evidence strength, not probabilities of causation.
"""

from math import isfinite

from backend.app.telemetry.incident import IncidentEvidence
from backend.app.telemetry.normalized import NormalizedTelemetry
from backend.app.telemetry.rca_models import (
    CONFIDENCE_DIMENSIONS,
    EvidenceConfidenceAssessment,
    RCACandidate,
)

WEIGHTS = {
    "direct_fault_evidence": 0.30,
    "temporal_relevance": 0.20,
    "topology_relevance": 0.15,
    "cross_source_corroboration": 0.15,
    "evidence_coverage": 0.10,
    "evidence_consistency": 0.10,
}

ERROR_TERMS = (
    "error",
    "failed",
    "failure",
    "exception",
    "timeout",
    "unavailable",
    "connection refused",
)

SEVERE_CONTRADICTION_TERMS = (
    "not reproducible",
    "failure ruled out",
    "dependency healthy",
)


def _event_key(event_id: object) -> str:
    return str(event_id)


def _is_error(event: NormalizedTelemetry) -> bool:
    if (event.status or "").upper() == "ERROR":
        return True
    if event.event_type == "log":
        message = (event.message or "").lower()
        return any(term in message for term in ERROR_TERMS)
    return False


def _unique_events(
    events: list[NormalizedTelemetry],
) -> list[NormalizedTelemetry]:
    """Deduplicate by event ID so repeated references do not inflate scores."""
    unique = {}
    for event in events:
        unique.setdefault(_event_key(event.event_id), event)
    return list(unique.values())


def assess_evidence_confidence(
    evidence: IncidentEvidence,
    candidate: RCACandidate,
) -> EvidenceConfidenceAssessment:
    """Assess evidence quality for one existing RCA candidate.

    This function does not modify the candidate or its D2.5 ranking score.
    """
    events = _unique_events(evidence.telemetry_events)
    candidate_events = [
        event for event in events
        if event.service_name == candidate.service_name
    ]

    supporting_ids = {
        _event_key(value) for value in candidate.supporting_evidence_ids
    }
    supported_candidate_events = [
        event for event in candidate_events
        if _event_key(event.event_id) in supporting_ids
    ]
    contradictory_ids = {
        _event_key(value) for value in candidate.contradictory_evidence_ids
    }

    limitations: list[str] = []
    if candidate_events and supporting_ids and not supported_candidate_events:
        limitations.append(
            "Candidate supporting evidence IDs did not match telemetry "
            "events emitted by the candidate service."
        )

    quality: dict[str, float | None] = {
        name: None for name in CONFIDENCE_DIMENSIONS
    }

    # Direct evidence is assessable when candidate telemetry exists.
    if candidate_events:
        direct_errors = [
            event for event in supported_candidate_events if _is_error(event)
        ]
        quality["direct_fault_evidence"] = (
            100.0 if direct_errors else 0.0
        )
    else:
        limitations.append(
            "No telemetry directly emitted by the candidate service was available."
        )

    # Temporal relevance requires a temporal result and relevant events.
    if evidence.temporal_analysis is not None:
        temporal_by_id = {
            _event_key(item.event_id): item
            for item in evidence.temporal_analysis.events
        }
        relevant_errors = [
            event for event in supported_candidate_events
            if _is_error(event)
            and _event_key(event.event_id) in temporal_by_id
        ]
        if relevant_errors:
            positions = {
                temporal_by_id[_event_key(event.event_id)].position
                for event in relevant_errors
            }
            quality["temporal_relevance"] = (
                100.0 if positions & {"BEFORE", "AT"} else 0.0
            )
        elif candidate_events:
            quality["temporal_relevance"] = 0.0
        else:
            limitations.append(
                "Temporal relevance could not be assessed without candidate telemetry."
            )
    else:
        limitations.append("Temporal analysis was unavailable.")

    # Topology is context only; it cannot establish that a service is faulty.
    if evidence.topology is not None:
        known_services = {
            item.service_name for item in evidence.topology.services
        }
        dependency_pairs = {
            (edge.source_service, edge.target_service)
            for edge in evidence.topology.dependencies
        }
        incident_service = evidence.incident.service_name
        candidate_name = candidate.service_name
        related = (
            candidate_name in known_services
            and (
                candidate_name == incident_service
                or (incident_service, candidate_name) in dependency_pairs
                or (candidate_name, incident_service) in dependency_pairs
                or candidate_name in evidence.upstream_dependencies
                or candidate_name in evidence.downstream_impact
            )
        )
        quality["topology_relevance"] = 100.0 if related else 0.0
    else:
        limitations.append("Topology was unavailable.")

    # Corroboration requires distinct telemetry types, not duplicate IDs.
    if candidate_events:
        types_with_faults = {
            event.event_type
            for event in supported_candidate_events
            if _is_error(event)
        }
        quality["cross_source_corroboration"] = min(
            100.0, max(0.0, (len(types_with_faults) - 1) * 50.0)
        )
        if len(types_with_faults) < 2:
            limitations.append(
                "Independent cross-source corroboration was limited."
            )
    else:
        limitations.append(
            "Cross-source corroboration could not be assessed."
        )

    # Coverage is based on whether relevant source categories are available.
    available_sources = 0
    total_sources = 2

    if "telemetry" not in evidence.unavailable_sources and evidence.telemetry_events:
        available_sources += 1
    if (
        "topology" not in evidence.unavailable_sources
        and evidence.topology is not None
    ):
        available_sources += 1

    quality["evidence_coverage"] = (
        available_sources / total_sources * 100.0
    )

    # Assess only explicit, traceable contradictions. Do not infer them
    # from missing telemetry or a healthy event alone.
    if contradictory_ids:
        conflicting = [
            event for event in events
            if _event_key(event.event_id) in contradictory_ids
        ]
        if conflicting:
            severe = any(
                any(
                    term in (event.message or "").lower()
                    for term in SEVERE_CONTRADICTION_TERMS
                )
                for event in conflicting
            )
            quality["evidence_consistency"] = 0.0 if severe else 50.0
            if severe:
                limitations.append(
                    "Explicit contradictory evidence requires investigation."
                )
        else:
            limitations.append(
                "Contradictory evidence IDs could not be matched to retrieved events."
            )
    else:
        quality["evidence_consistency"] = None
        limitations.append(
            "No explicit contradiction assessment was available; "
            "absence of recorded contradictions does not establish consistency."
        )

    weighted_score = sum(
        (quality[name] or 0.0) * WEIGHTS[name]
        for name in CONFIDENCE_DIMENSIONS
    )
    score = round(max(0.0, min(100.0, weighted_score)), 2)

    coverage = quality["evidence_coverage"] or 0.0
    direct = quality["direct_fault_evidence"]
    corroboration = quality["cross_source_corroboration"]
    consistency = quality["evidence_consistency"]

    high_eligible = (
        score >= 70.0
        and coverage >= 70.0
        and direct is not None
        and direct >= 60.0
        and corroboration is not None
        and corroboration >= 50.0
        and consistency is not None
        and consistency > 0.0
    )

    if score < 40.0:
        level = "LOW"
    elif score < 70.0 or not high_eligible:
        level = "MODERATE"
    else:
        level = "HIGH"

    if not isfinite(score):
        raise ValueError("Calculated confidence score must be finite")

    return EvidenceConfidenceAssessment(
        confidence_score=score,
        confidence_level=level,
        evidence_quality=quality,
        confidence_limitations=sorted(set(limitations)),
    )
