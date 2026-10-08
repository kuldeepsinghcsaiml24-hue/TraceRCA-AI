from neo4j import AsyncDriver, AsyncGraphDatabase

from backend.app.core.config import settings


class Neo4jConnection:
    """
    Manages the Neo4j asynchronous database connection.
    """

    def __init__(self) -> None:
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Create the Neo4j driver."""

        self.driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(
                settings.neo4j_username,
                settings.neo4j_password,
            ),
        )

        await self.driver.verify_connectivity()

    async def close(self) -> None:
        """Close the Neo4j driver."""

        if self.driver is not None:
            await self.driver.close()
            self.driver = None


neo4j_connection = Neo4jConnection()