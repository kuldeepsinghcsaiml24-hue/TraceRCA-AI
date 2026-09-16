import pytest

from backend.app.cache.redis_client import RedisClient


@pytest.mark.asyncio
async def test_redis_connection() -> None:
    """Verify that the application can connect to Redis."""

    redis_client = RedisClient()

    await redis_client.connect()

    await redis_client.set("tracerca:test", "hello")
    value = await redis_client.get("tracerca:test")

    assert value == "hello"

    await redis_client.delete("tracerca:test")

    assert await redis_client.get("tracerca:test") is None

    await redis_client.close()