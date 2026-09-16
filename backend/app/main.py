from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes.health import router as health_router
from .cache.dependencies import redis_client
from .core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""

    await redis_client.connect()

    yield

    await redis_client.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Distributed OpenTelemetry Multi-Layer Causal Inference "
        "& Auto-Healing Engine"
    ),
    lifespan=lifespan,
)

app.include_router(health_router)