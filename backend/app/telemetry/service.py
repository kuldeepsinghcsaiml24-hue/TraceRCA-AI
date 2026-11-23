import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import TelemetryEvent
from .normalizers import normalize_event
from .schemas import (
    LogIngestRequest,
    MetricIngestRequest,
    TraceIngestRequest,
)
from .topology_builder import topology_builder

logger = logging.getLogger(__name__)


async def _update_topology(
    db: AsyncSession,
    event: TelemetryEvent,
) -> None:
    """
    Update Neo4j after PostgreSQL has committed an event.

    Topology failures are logged and do not invalidate a
    successfully persisted telemetry event.
    """
    try:
        normalized = normalize_event(event)

        # Ensure the service node exists.
        await topology_builder.process_event(normalized)

        if event.event_type != "trace":
            return

        if not event.trace_id or not event.span_id:
            return

        # Find the parent span, if it already exists.
        if event.parent_span_id:
            result = await db.execute(
                select(TelemetryEvent).where(
                    TelemetryEvent.event_type == "trace",
                    TelemetryEvent.trace_id == event.trace_id,
                    TelemetryEvent.span_id == event.parent_span_id,
                )
            )
            parent_event = result.scalar_one_or_none()

            if parent_event is not None:
                parent = normalize_event(parent_event)

                await topology_builder.process_event(parent)
                await topology_builder.create_dependency_from_trace(
                    parent,
                    normalized,
                )

        # Find children that arrived before this parent.
        result = await db.execute(
            select(TelemetryEvent).where(
                TelemetryEvent.event_type == "trace",
                TelemetryEvent.trace_id == event.trace_id,
                TelemetryEvent.parent_span_id == event.span_id,
            )
        )
        child_events = result.scalars().all()

        for child_event in child_events:
            child = normalize_event(child_event)

            await topology_builder.process_event(child)
            await topology_builder.create_dependency_from_trace(
                normalized,
                child,
            )

    except Exception:
        logger.exception(
            "Topology update failed for telemetry event %s",
            event.id,
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
        operation_name=data.operation_name,
        duration_ms=data.duration_ms,
        status=data.status,
        attributes=data.attributes,
    )

    try:
        db.add(event)
        await db.commit()
        await db.refresh(event)
    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise

    await _update_topology(db, event)
    return event


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
    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise

    await _update_topology(db, event)
    return event


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
    except (SQLAlchemyError, OSError):
        await db.rollback()
        raise

    await _update_topology(db, event)
    return event