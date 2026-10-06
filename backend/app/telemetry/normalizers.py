from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalized import NormalizedTelemetry


def normalize_trace(event: TelemetryEvent) -> NormalizedTelemetry:
    """
    Convert a persisted trace telemetry event into the
    common NormalizedTelemetry representation.
    """

    if event.event_type != "trace":
        raise ValueError("Expected a trace telemetry event")

    return NormalizedTelemetry(
        event_id=event.id,
        event_type="trace",
        timestamp=event.timestamp,
        service_name=event.service_name,
        operation_name=event.operation_name,
        trace_id=event.trace_id,
        span_id=event.span_id,
        parent_span_id=event.parent_span_id,
        duration_ms=event.duration_ms,
        status=event.status,
        attributes=event.attributes or {},
    )