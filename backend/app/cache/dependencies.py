from .redis_client import RedisClient


redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Provide the Redis client to FastAPI routes."""

    return redis_client