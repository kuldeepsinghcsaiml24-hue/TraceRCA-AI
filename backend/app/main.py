from contextlib import asynccontextmanager

from fastapi import FastAPI
from .api.routes.dashboard import router as dashboard_router

from .api.routes.health import router as health_router
from .api.routes.telemetry import router as telemetry_router
from .cache.dependencies import redis_client
from .core.config import settings
from .telemetry.tracing import configure_tracing
from .db.neo4j import neo4j_connection
from fastapi.middleware.cors import CORSMiddleware



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""

    configure_tracing(settings.otel_service_name)

    await redis_client.connect()
    await neo4j_connection.connect()

    try:
        yield
    finally:
        await neo4j_connection.close()
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(telemetry_router)
app.include_router(dashboard_router)