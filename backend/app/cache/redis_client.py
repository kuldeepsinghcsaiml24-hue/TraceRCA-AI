import redis.asyncio as redis

from ..core.config import settings


class RedisClient:
    """Provide a small abstraction around Redis operations."""

    def __init__(self) -> None:
        self.client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    async def connect(self) -> None:
        """Verify the Redis connection."""

        await self.client.ping()

    async def set(
        self,
        key: str,
        value: str,
        expiration: int | None = None,
    ) -> None:
        """Store a value in Redis."""

        await self.client.set(key, value, ex=expiration)

    async def get(self, key: str) -> str | None:
        """Retrieve a value from Redis."""

        return await self.client.get(key)

    async def delete(self, key: str) -> None:
        """Delete a value from Redis."""

        await self.client.delete(key)

    async def close(self) -> None:
        """Close the Redis connection."""

        await self.client.aclose()