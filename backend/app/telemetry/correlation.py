from datetime import timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from backend.app.telemetry.normalized import NormalizedTelemetry


class CorrelationResult(BaseModel):
    """
    Represents a correlation relationship between two
    normalized telemetry events.
    """

    source_event_id: UUID
    target_event_id: UUID

    correlation_type: Literal[
        "trace_id",
        "span_id",
        "service_time",
    ]

    strength: Literal[
        "VERY_STRONG",
        "STRONG",
        "MEDIUM",
    ]

    reason: str


def correlate_trace_log(
    trace: NormalizedTelemetry,
    log: NormalizedTelemetry,
) -> CorrelationResult | None:
    """
    Correlate a trace event with a log event.

    Correlation priority:

    1. Same trace_id + same span_id -> VERY_STRONG
    2. Same trace_id -> STRONG
    3. Otherwise -> no correlation
    """

    if trace.event_type != "trace":
        raise ValueError("Expected a trace event")

    if log.event_type != "log":
        raise ValueError("Expected a log event")

    if not trace.trace_id or not log.trace_id:
        return None

    if trace.trace_id != log.trace_id:
        return None

    # Most specific correlation:
    # same trace and same span.
    if (
        trace.span_id
        and log.span_id
        and trace.span_id == log.span_id
    ):
        return CorrelationResult(
            source_event_id=trace.event_id,
            target_event_id=log.event_id,
            correlation_type="span_id",
            strength="VERY_STRONG",
            reason="Same trace_id and span_id",
        )

    # Same trace but different/missing span ID.
    return CorrelationResult(
        source_event_id=trace.event_id,
        target_event_id=log.event_id,
        correlation_type="trace_id",
        strength="STRONG",
        reason="Same trace_id",
    )


def correlate_trace_metric(
    trace: NormalizedTelemetry,
    metric: NormalizedTelemetry,
) -> CorrelationResult | None:
    """
    Correlate a trace event with a metric event using
    service name and timestamp proximity.

    A correlation is created when both events belong to
    the same service and occur within 5 seconds of each other.
    """

    if trace.event_type != "trace":
        raise ValueError("Expected a trace event")

    if metric.event_type != "metric":
        raise ValueError("Expected a metric event")

    if trace.service_name != metric.service_name:
        return None

    time_difference = abs(
        trace.timestamp - metric.timestamp
    )

    if time_difference > timedelta(seconds=5):
        return None

    return CorrelationResult(
        source_event_id=trace.event_id,
        target_event_id=metric.event_id,
        correlation_type="service_time",
        strength="MEDIUM",
        reason="Same service within 5 seconds",
    )


def correlate_by_service_time(
    source: NormalizedTelemetry,
    target: NormalizedTelemetry,
) -> CorrelationResult | None:
    """
    Correlate two normalized telemetry events using
    service name and timestamp proximity.

    Events are correlated when they belong to the same
    service and occur within 5 seconds of each other.
    """

    if source.service_name != target.service_name:
        return None

    time_difference = abs(
        source.timestamp - target.timestamp
    )

    if time_difference > timedelta(seconds=5):
        return None

    return CorrelationResult(
        source_event_id=source.event_id,
        target_event_id=target.event_id,
        correlation_type="service_time",
        strength="MEDIUM",
        reason="Same service within 5 seconds",
    )