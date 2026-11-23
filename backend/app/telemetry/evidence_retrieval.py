from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.incident import IncidentContext


DEFAULT_MAX_EVIDENCE_EVENTS = 500


async def retrieve_telemetry_events(
    db: AsyncSession,
    incident: IncidentContext,
    limit: int = DEFAULT_MAX_EVIDENCE_EVENTS,
) -> list[TelemetryEvent]:
    """
    Retrieve bounded telemetry for an incident and related services.

    First retrieves events for the incident service. If capacity remains,
    it retrieves cross-service events sharing those events' trace IDs.
    Both queries use the incident time window.
    """
    if limit < 1:
        raise ValueError("limit must be greater than zero")

    time_filters = (
        TelemetryEvent.timestamp >= incident.start_time,
        TelemetryEvent.timestamp <= incident.end_time,
    )

    primary_result = await db.execute(
        select(TelemetryEvent)
        .where(
            TelemetryEvent.service_name == incident.service_name,
            *time_filters,
        )
        .order_by(
            TelemetryEvent.timestamp.asc(),
            TelemetryEvent.id.asc(),
        )
        .limit(limit)
    )

    primary_events = list(primary_result.scalars().all())
    remaining = limit - len(primary_events)

    if remaining <= 0:
        return primary_events[:limit]

    trace_ids = sorted({
        event.trace_id
        for event in primary_events
        if event.trace_id
    })

    if not trace_ids:
        return primary_events

    related_result = await db.execute(
        select(TelemetryEvent)
        .where(
            *time_filters,
            TelemetryEvent.service_name != incident.service_name,
            TelemetryEvent.trace_id.in_(trace_ids),
        )
        .order_by(
            TelemetryEvent.timestamp.asc(),
            TelemetryEvent.id.asc(),
        )
        .limit(remaining)
    )

    related_events = list(related_result.scalars().all())

    # Keep the combined result bounded and deterministically ordered.
    events_by_id = {
        event.id: event
        for event in [*primary_events, *related_events]
    }

    return sorted(
        events_by_id.values(),
        key=lambda event: (event.timestamp, event.id),
    )[:limit]
