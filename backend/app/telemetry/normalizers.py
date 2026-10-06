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

def normalize_log(event: TelemetryEvent) -> NormalizedTelemetry:
    """
    Convert a persisted log telemetry event into the
    common NormalizedTelemetry representation.
    """

    if event.event_type != "log":
        raise ValueError("Expected a log telemetry event")

    return NormalizedTelemetry(
        event_id=event.id,
        event_type="log",
        timestamp=event.timestamp,
        service_name=event.service_name,
        trace_id=event.trace_id,
        span_id=event.span_id,
        message=event.message,
        attributes=event.attributes or {},
    )

def normalize_metric(event: TelemetryEvent) -> NormalizedTelemetry:
    """
    Convert a persisted metric telemetry event into the
    common NormalizedTelemetry representation.
    """

    if event.event_type != "metric":
        raise ValueError("Expected a metric telemetry event")

    return NormalizedTelemetry(
        event_id=event.id,
        event_type="metric",
        timestamp=event.timestamp,
        service_name=event.service_name,
        metric_name=event.metric_name,
        metric_value=event.metric_value,
        attributes=event.attributes or {},
    )

def normalize_event(event: TelemetryEvent) -> NormalizedTelemetry:
    """
    Normalize a telemetry event using the appropriate
    event-specific normalizer.
    """

    if event.event_type == "trace":
        return normalize_trace(event)

    if event.event_type == "log":
        return normalize_log(event)

    if event.event_type == "metric":
        return normalize_metric(event)

    raise ValueError(
        f"Unsupported telemetry event type: {event.event_type}"
    )