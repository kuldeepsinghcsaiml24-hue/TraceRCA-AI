from backend.app.db.neo4j import neo4j_connection
from backend.app.telemetry.topology import (
    DependencyEdge,
    ServiceNode,
    TopologyResponse,
)


class TopologyService:
    """
    Handles service topology operations in Neo4j.
    """

    async def upsert_service_node(
        self,
        service: ServiceNode,
    ) -> None:
        """
        Create or update a service node in Neo4j.

        If the service already exists, its first_seen and
        last_seen timestamps are updated without creating
        a duplicate node.
        """

        if neo4j_connection.driver is None:
            raise RuntimeError(
                "Neo4j connection is not initialized"
            )

        query = """
        MERGE (s:Service {
            service_name: $service_name
        })

        ON CREATE SET
            s.first_seen = $first_seen,
            s.last_seen = $last_seen

        ON MATCH SET
            s.first_seen = CASE
                WHEN s.first_seen > $first_seen
                THEN $first_seen
                ELSE s.first_seen
            END,

            s.last_seen = CASE
                WHEN s.last_seen < $last_seen
                THEN $last_seen
                ELSE s.last_seen
            END
        """

        async with neo4j_connection.driver.session() as session:
            result = await session.run(
                query,
                service_name=service.service_name,
                first_seen=service.first_seen,
                last_seen=service.last_seen,
            )

            await result.consume()

    async def upsert_dependency_edge(
        self,
        dependency: DependencyEdge,
    ) -> None:
        """
        Create or update a dependency relationship in Neo4j.

        Repeated observations of the same source and target
        services update the existing relationship instead of
        creating a duplicate.
        """

        if neo4j_connection.driver is None:
            raise RuntimeError(
                "Neo4j connection is not initialized"
            )

        query = """
        MATCH (source:Service {
            service_name: $source_service
        })

        MATCH (target:Service {
            service_name: $target_service
        })

        MERGE (source)-[d:DEPENDS_ON]->(target)

        ON CREATE SET
            d.first_seen = $first_seen,
            d.last_seen = $last_seen

        ON MATCH SET
            d.first_seen = CASE
                WHEN d.first_seen > $first_seen
                THEN $first_seen
                ELSE d.first_seen
            END,

            d.last_seen = CASE
                WHEN d.last_seen < $last_seen
                THEN $last_seen
                ELSE d.last_seen
            END
        """

        async with neo4j_connection.driver.session() as session:
            result = await session.run(
                query,
                source_service=dependency.source_service,
                target_service=dependency.target_service,
                first_seen=dependency.first_seen,
                last_seen=dependency.last_seen,
            )

            await result.consume()

    async def get_topology(self) -> TopologyResponse:
        """
        Retrieve the complete service topology from Neo4j.
        """

        if neo4j_connection.driver is None:
            raise RuntimeError(
                "Neo4j connection is not initialized"
            )

        services: list[ServiceNode] = []
        dependencies: list[DependencyEdge] = []

        async with neo4j_connection.driver.session() as session:
            service_result = await session.run(
                """
                MATCH (s:Service)
                RETURN
                    s.service_name AS service_name,
                    s.first_seen AS first_seen,
                    s.last_seen AS last_seen
                ORDER BY s.service_name
                """
            )

            service_records = await service_result.data()

            for record in service_records:
                services.append(
                    ServiceNode(
                        service_name=record["service_name"],
                        first_seen=record["first_seen"].to_native(),
                        last_seen=record["last_seen"].to_native(),
                    )
                )

            dependency_result = await session.run(
                """
                MATCH (
                    source:Service
                )-[d:DEPENDS_ON]->(
                    target:Service
                )
                RETURN
                    source.service_name AS source_service,
                    target.service_name AS target_service,
                    d.first_seen AS first_seen,
                    d.last_seen AS last_seen
                ORDER BY
                    source_service,
                    target_service
                """
            )

            dependency_records = await dependency_result.data()

            for record in dependency_records:
                dependencies.append(
                    DependencyEdge(
                        source_service=record["source_service"],
                        target_service=record["target_service"],
                        first_seen=record["first_seen"].to_native(),
                        last_seen=record["last_seen"].to_native(),
                    )
                )

        return TopologyResponse(
            services=services,
            dependencies=dependencies,
        )


topology_service = TopologyService()