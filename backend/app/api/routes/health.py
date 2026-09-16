from fastapi import APIRouter

from ...core.config import settings


router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return the health status of the TraceRCA AI backend."""

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }