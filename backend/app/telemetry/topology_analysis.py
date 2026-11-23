from backend.app.telemetry.topology import TopologyResponse


def get_upstream_dependencies(
    topology: TopologyResponse,
    service_name: str,
    max_depth: int = 2,
) -> list[str]:
    """Return direct and transitive dependencies of a service.

    A directed edge A -> B means service A depends on service B.
    Results are sorted by traversal depth, then service name.
    This describes topology, not causal proof.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    known_services = {
        service.service_name for service in topology.services
    }
    if service_name not in known_services:
        return []

    upstream_by_source: dict[str, list[str]] = {}
    for edge in topology.dependencies:
        upstream_by_source.setdefault(
            edge.source_service, []
        ).append(edge.target_service)

    for targets in upstream_by_source.values():
        targets.sort()

    visited = {service_name}
    results: list[str] = []
    frontier = [service_name]

    for _depth in range(1, max_depth + 1):
        next_frontier: list[str] = []

        for current in sorted(frontier):
            for dependency in upstream_by_source.get(current, []):
                if dependency in visited:
                    continue

                visited.add(dependency)
                results.append(dependency)
                next_frontier.append(dependency)

        frontier = next_frontier
        if not frontier:
            break

    return results

def get_downstream_impact(
    topology: TopologyResponse,
    service_name: str,
    max_depth: int = 2,
) -> list[str]:
    """Return direct and transitive services depending on a service.

    For an edge A -> B, A depends on B. Downstream traversal
    therefore follows edges in reverse, from B to A.
    Results are ordered by traversal depth, then service name.
    Potential impact does not establish causation.
    """
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    known_services = {
        service.service_name for service in topology.services
    }
    if service_name not in known_services:
        return []

    downstream_by_target: dict[str, list[str]] = {}
    for edge in topology.dependencies:
        downstream_by_target.setdefault(
            edge.target_service, []
        ).append(edge.source_service)

    for sources in downstream_by_target.values():
        sources.sort()

    visited = {service_name}
    results: list[str] = []
    frontier = [service_name]

    for _depth in range(1, max_depth + 1):
        next_frontier: list[str] = []

        for current in sorted(frontier):
            for dependent in downstream_by_target.get(current, []):
                if dependent in visited:
                    continue

                visited.add(dependent)
                results.append(dependent)
                next_frontier.append(dependent)

        frontier = next_frontier
        if not frontier:
            break

    return results