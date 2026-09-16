import pytest
from sqlalchemy import text

from backend.app.db.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_database_connection() -> None:
    """Verify that the application can connect to PostgreSQL."""

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1