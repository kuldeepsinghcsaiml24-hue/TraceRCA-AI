"""Bounded graph evidence retrieval for RCA candidate explanations."""

from collections import deque
from typing import Any

from backend.app.telemetry.topology import TopologyResponse


def retrieve_candidate_graph_evidence(
    topology: TopologyResponse | None,
    incident_service: str,
    candidate_service: str,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Find a shortest path using actual edges in the retrieved topology.

    A directed edge A -> B means A depends on B. Paths may be traversed
    in either direction to describe relationships, but each returned edge
    retains its actual direction. A path describes topology, not causation.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    if topology is None:
        return {
            "status": "TOPOLOGY_UNAVAILABLE",
            "incident_service": incident_service,
            "candidate_service": candidate_service,
            "path_services": [],
            "path_edges": [],
            "relationship": "UNKNOWN",
        }

    known_services = {
        service.service_name for service in topology.services
    }

    if (
        incident_service not in known_services
        or candidate_service not in known_services
    ):
        return {
            "status": "SERVICE_NOT_IN_TOPOLOGY",
            "incident_service": incident_service,
            "candidate_service": candidate_service,
            "path_services": [],
            "path_edges": [],
            "relationship": "UNKNOWN",
        }

    if incident_service == candidate_service:
        return {
            "status": "FOUND",
            "incident_service": incident_service,
            "candidate_service": candidate_service,
            "path_services": [incident_service],
            "path_edges": [],
            "relationship": "INCIDENT_SERVICE",
        }

    adjacency: dict[str, list[tuple[str, Any, str]]] = {}

    for edge in topology.dependencies:
        adjacency.setdefault(edge.source_service, []).append(
            (edge.target_service, edge, "WITH_DEPENDENCY_DIRECTION")
        )
        adjacency.setdefault(edge.target_service, []).append(
            (edge.source_service, edge, "AGAINST_DEPENDENCY_DIRECTION")
        )

    for neighbors in adjacency.values():
        neighbors.sort(key=lambda item: (item[0], item[1].source_service,
                                         item[1].target_service))

    # Search from the candidate toward the incident, without exceeding
    # max_depth edges. Visited nodes prevent cycles.
    queue = deque([(candidate_service, [candidate_service], [])])
    visited = {candidate_service}

    while queue:
        current, path_services, path_edges = queue.popleft()
        depth = len(path_edges)

        if depth >= max_depth:
            continue

        for neighbor, edge, traversal in adjacency.get(current, []):
            if neighbor in visited:
                continue

            next_services = path_services + [neighbor]
            next_edges = path_edges + [
                {
                    "source_service": edge.source_service,
                    "target_service": edge.target_service,
                    "first_seen": edge.first_seen.isoformat(),
                    "last_seen": edge.last_seen.isoformat(),
                    "traversal": traversal,
                }
            ]

            if neighbor == incident_service:
                relationship = (
                    "DIRECT_DEPENDENCY"
                    if len(next_edges) == 1
                    else "INDIRECT_DEPENDENCY"
                )
                return {
                    "status": "FOUND",
                    "incident_service": incident_service,
                    "candidate_service": candidate_service,
                    "path_services": next_services,
                    "path_edges": next_edges,
                    "relationship": relationship,
                }

            visited.add(neighbor)
            queue.append((neighbor, next_services, next_edges))

    return {
        "status": "NO_PATH_FOUND",
        "incident_service": incident_service,
        "candidate_service": candidate_service,
        "path_services": [],
        "path_edges": [],
        "relationship": "UNKNOWN",
    }
