from backend.app.telemetry.normalized import NormalizedTelemetry
from backend.app.telemetry.topology import (
    DependencyEdge,
    ServiceNode,
)
from backend.app.telemetry.topology_service import topology_service


class TopologyBuilder:
    """
    Builds the service topology from normalized telemetry.
    """

    async def process_event(
        self,
        event: NormalizedTelemetry,
    ) -> None:
        """
        Process one normalized telemetry event.

        The event contributes its service to the topology.
        Trace events can also create dependency relationships
        based on parent/child span relationships.
        """

        if not event.service_name:
            return

        service = ServiceNode(
            service_name=event.service_name,
            first_seen=event.timestamp,
            last_seen=event.timestamp,
        )

        await topology_service.upsert_service_node(service)

    async def process_events(
        self,
        events: list[NormalizedTelemetry],
    ) -> None:
        """
        Process multiple normalized telemetry events.
        """

        for event in events:
            await self.process_event(event)

    async def create_dependency_from_trace(
        self,
        parent_span: NormalizedTelemetry,
        child_span: NormalizedTelemetry,
    ) -> None:
        """
        Create a service dependency from a trace parent/child
        relationship.

        The parent service is considered dependent on the
        child service when the two spans belong to different
        services.
        """

        if parent_span.event_type != "trace":
            raise ValueError("Parent event must be a trace")

        if child_span.event_type != "trace":
            raise ValueError("Child event must be a trace")

        if not parent_span.service_name:
            return

        if not child_span.service_name:
            return

        if parent_span.service_name == child_span.service_name:
            return

        dependency = DependencyEdge(
            source_service=parent_span.service_name,
            target_service=child_span.service_name,
            first_seen=min(
                parent_span.timestamp,
                child_span.timestamp,
            ),
            last_seen=max(
                parent_span.timestamp,
                child_span.timestamp,
            ),
        )

        await topology_service.upsert_dependency_edge(
            dependency
        )


topology_builder = TopologyBuilder()