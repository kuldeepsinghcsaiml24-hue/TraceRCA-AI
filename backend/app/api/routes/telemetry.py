from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...telemetry.schemas import (
    LogIngestRequest,
    MetricIngestRequest,
    TraceIngestRequest,
)
from ...telemetry.service import (
    ingest_log,
    ingest_metric,
    ingest_trace,
)

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


@router.post("/traces", status_code=status.HTTP_201_CREATED)
async def create_trace(
    data: TraceIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest and persist a distributed trace span."""
    try:
        event = await ingest_trace(db, data)
    except (SQLAlchemyError, OSError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry event",
        )

    return {
        "status": "accepted",
        "event_id": event.id,
        "event_type": event.event_type,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
    }


@router.post("/logs", status_code=status.HTTP_201_CREATED)
async def create_log(
    data: LogIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest and persist a log event."""
    try:
        event = await ingest_log(db, data)
    except (SQLAlchemyError, OSError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry event",
        )

    return {
        "status": "accepted",
        "event_id": event.id,
        "event_type": event.event_type,
        "service_name": event.service_name,
        "trace_id": event.trace_id,
        "span_id": event.span_id,
    }


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
async def create_metric(
    data: MetricIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest and persist a metric event."""
    try:
        event = await ingest_metric(db, data)
    except (SQLAlchemyError, OSError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry event",
        )

    return {
        "status": "accepted",
        "event_id": event.id,
        "event_type": event.event_type,
        "service_name": event.service_name,
        "metric_name": event.metric_name,
        "metric_value": event.metric_value,
    }