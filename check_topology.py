import asyncio
import traceback

from backend.app.db.neo4j import neo4j_connection
from backend.app.telemetry.topology_service import topology_service


async def main():
    try:
        await neo4j_connection.connect()
        print("Neo4j connection initialized.")

        topology = await topology_service.get_topology()

        print("Services:", len(topology.services))
        for service in topology.services:
            print(" -", service.service_name)

        print("Dependencies:", len(topology.dependencies))
        for dependency in topology.dependencies:
            print(
                f" - {dependency.source_service}"
                f" -> {dependency.target_service}"
            )

    except Exception:
        traceback.print_exc()

    finally:
        await neo4j_connection.close()


if __name__ == "__main__":
    asyncio.run(main())
