from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import TelemetryEvent
from .schemas import (
    LogIngestRequest,
    MetricIngestRequest,
    TraceIngestRequest,
)


async def ingest_trace(
    db: AsyncSession,
    data: TraceIngestRequest,
) -> TelemetryEvent:
    """Convert and persist an incoming trace."""
    event = TelemetryEvent(
        event_type="trace",
        timestamp=data.timestamp,
        service_name=data.service_name,
        trace_id=data.trace_id,
        span_id=data.span_id,
        parent_span_id=data.parent_span_id,
        attributes=data.attributes,
    )

    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise


async def ingest_log(
    db: AsyncSession,
    data: LogIngestRequest,
) -> TelemetryEvent:
    """Convert and persist an incoming log."""
    event = TelemetryEvent(
        event_type="log",
        timestamp=data.timestamp,
        service_name=data.service_name,
        trace_id=data.trace_id,
        span_id=data.span_id,
        message=data.message,
        attributes=data.attributes,
    )

    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise


async def ingest_metric(
    db: AsyncSession,
    data: MetricIngestRequest,
) -> TelemetryEvent:
    """Convert and persist an incoming metric."""
    event = TelemetryEvent(
        event_type="metric",
        timestamp=data.timestamp,
        service_name=data.service_name,
        metric_name=data.metric_name,
        metric_value=data.metric_value,
        attributes=data.attributes,
    )

    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        return event

    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise