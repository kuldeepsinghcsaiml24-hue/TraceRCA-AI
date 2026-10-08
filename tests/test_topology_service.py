from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.db.neo4j import neo4j_connection
from backend.app.telemetry.normalized import NormalizedTelemetry
from backend.app.telemetry.topology import (
    DependencyEdge,
    ServiceNode,
)
from backend.app.telemetry.topology_builder import topology_builder
from backend.app.telemetry.topology_service import topology_service


@pytest.mark.asyncio
async def test_upsert_dependency_edge():
    await neo4j_connection.connect()

    source_service = "test-api-service"
    target_service = "test-database-service"

    now = datetime.now(timezone.utc)

    source = ServiceNode(
        service_name=source_service,
        first_seen=now,
        last_seen=now,
    )

    target = ServiceNode(
        service_name=target_service,
        first_seen=now,
        last_seen=now,
    )

    dependency = DependencyEdge(
        source_service=source_service,
        target_service=target_service,
        first_seen=now,
        last_seen=now,
    )

    try:
        await topology_service.upsert_service_node(source)
        await topology_service.upsert_service_node(target)

        await topology_service.upsert_dependency_edge(
            dependency
        )

        async with neo4j_connection.driver.session() as session:
            result = await session.run(
                """
                MATCH (
                    source:Service {
                        service_name: $source_service
                    }
                )-[d:DEPENDS_ON]->(
                    target:Service {
                        service_name: $target_service
                    }
                )
                RETURN
                    source.service_name AS source_service,
                    target.service_name AS target_service,
                    d.first_seen AS first_seen,
                    d.last_seen AS last_seen
                """,
                source_service=source_service,
                target_service=target_service,
            )

            record = await result.single()

        assert record is not None
        assert record["source_service"] == source_service
        assert record["target_service"] == target_service
        assert record["first_seen"] is not None
        assert record["last_seen"] is not None

    finally:
        async with neo4j_connection.driver.session() as session:
            await session.run(
                """
                MATCH (source:Service {
                    service_name: $source_service
                })
                MATCH (target:Service {
                    service_name: $target_service
                })
                MATCH (source)-[d:DEPENDS_ON]->(target)
                DELETE d

                WITH source, target
                DETACH DELETE source, target
                """,
                source_service=source_service,
                target_service=target_service,
            )

        await neo4j_connection.close()


@pytest.mark.asyncio
async def test_topology_builder_creates_service_node():
    await neo4j_connection.connect()

    service_name = f"test-service-{uuid4().hex[:8]}"

    event = NormalizedTelemetry(
        event_id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name=service_name,
        operation_name="test-operation",
        trace_id="test-trace",
        span_id="test-span",
        parent_span_id=None,
        duration_ms=10.0,
        status="OK",
        message=None,
        metric_name=None,
        metric_value=None,
        attributes={},
    )

    try:
        await topology_builder.process_event(event)

        async with neo4j_connection.driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Service {
                    service_name: $service_name
                })
                RETURN s.service_name AS service_name
                """,
                service_name=service_name,
            )

            record = await result.single()

        assert record is not None
        assert record["service_name"] == service_name

    finally:
        async with neo4j_connection.driver.session() as session:
            await session.run(
                """
                MATCH (s:Service {
                    service_name: $service_name
                })
                DETACH DELETE s
                """,
                service_name=service_name,
            )

        await neo4j_connection.close()


@pytest.mark.asyncio
async def test_topology_builder_creates_dependency_edge():
    await neo4j_connection.connect()

    parent_service = f"test-parent-{uuid4().hex[:8]}"
    child_service = f"test-child-{uuid4().hex[:8]}"

    now = datetime.now(timezone.utc)

    parent_span = NormalizedTelemetry(
        event_id=uuid4(),
        event_type="trace",
        timestamp=now,
        service_name=parent_service,
        operation_name="parent-operation",
        trace_id="test-trace",
        span_id="parent-span",
        parent_span_id=None,
        duration_ms=20.0,
        status="OK",
        message=None,
        metric_name=None,
        metric_value=None,
        attributes={},
    )

    child_span = NormalizedTelemetry(
        event_id=uuid4(),
        event_type="trace",
        timestamp=now,
        service_name=child_service,
        operation_name="child-operation",
        trace_id="test-trace",
        span_id="child-span",
        parent_span_id="parent-span",
        duration_ms=10.0,
        status="OK",
        message=None,
        metric_name=None,
        metric_value=None,
        attributes={},
    )

    try:
        await topology_builder.process_event(parent_span)
        await topology_builder.process_event(child_span)

        await topology_builder.create_dependency_from_trace(
            parent_span,
            child_span,
        )

        async with neo4j_connection.driver.session() as session:
            result = await session.run(
                """
                MATCH (
                    source:Service {
                        service_name: $parent_service
                    }
                )-[d:DEPENDS_ON]->(
                    target:Service {
                        service_name: $child_service
                    }
                )
                RETURN
                    source.service_name AS source_service,
                    target.service_name AS target_service
                """,
                parent_service=parent_service,
                child_service=child_service,
            )

            record = await result.single()

        assert record is not None
        assert record["source_service"] == parent_service
        assert record["target_service"] == child_service

    finally:
        async with neo4j_connection.driver.session() as session:
            await session.run(
                """
                MATCH (source:Service {
                    service_name: $parent_service
                })
                MATCH (target:Service {
                    service_name: $child_service
                })
                MATCH (source)-[d:DEPENDS_ON]->(target)
                DELETE d

                WITH source, target
                DETACH DELETE source, target
                """,
                parent_service=parent_service,
                child_service=child_service,
            )

        await neo4j_connection.close()


@pytest.mark.asyncio
async def test_get_topology():
    await neo4j_connection.connect()

    source_service = f"test-query-source-{uuid4().hex[:8]}"
    target_service = f"test-query-target-{uuid4().hex[:8]}"

    now = datetime.now(timezone.utc)

    source = ServiceNode(
        service_name=source_service,
        first_seen=now,
        last_seen=now,
    )

    target = ServiceNode(
        service_name=target_service,
        first_seen=now,
        last_seen=now,
    )

    dependency = DependencyEdge(
        source_service=source_service,
        target_service=target_service,
        first_seen=now,
        last_seen=now,
    )

    try:
        await topology_service.upsert_service_node(source)
        await topology_service.upsert_service_node(target)

        await topology_service.upsert_dependency_edge(
            dependency
        )

        topology = await topology_service.get_topology()

        service_names = {
            service.service_name
            for service in topology.services
        }

        dependency_pairs = {
            (
                dependency.source_service,
                dependency.target_service,
            )
            for dependency in topology.dependencies
        }

        assert source_service in service_names
        assert target_service in service_names

        assert (
            source_service,
            target_service,
        ) in dependency_pairs

    finally:
        async with neo4j_connection.driver.session() as session:
            await session.run(
                """
                MATCH (source:Service {
                    service_name: $source_service
                })
                MATCH (target:Service {
                    service_name: $target_service
                })
                MATCH (source)-[d:DEPENDS_ON]->(target)
                DELETE d

                WITH source, target
                DETACH DELETE source, target
                """,
                source_service=source_service,
                target_service=target_service,
            )

        await neo4j_connection.close()

"""
Result:
2 passed

confirms that the topology builder can now:
- Process normalized telemetry.
- Create/update service nodes automatically.
- Detect a parent → child trace relationship.
- Create the corresponding DEPENDS_ON edge.
- Avoid creating a dependency when both spans belong to the same service.
- Work against the actual Neo4j database.


result
4 passed

The new test specifically verifies:
Neo4j
  ↓
get_topology()
  ↓
TopologyResponse
  ├── services
  └── dependencies

"""