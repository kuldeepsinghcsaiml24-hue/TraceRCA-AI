from datetime import datetime, timedelta, timezone

from backend.app.telemetry.correlation import correlate_trace_metric
from backend.app.telemetry.normalized import NormalizedTelemetry


def create_trace(
    service_name: str,
    timestamp: datetime,
):
    return NormalizedTelemetry(
        event_type="trace",
        timestamp=timestamp,
        service_name=service_name,
        trace_id="trace-123",
        operation_name="process-payment",
        status="ERROR",
    )


def create_metric(
    service_name: str,
    timestamp: datetime,
):
    return NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp,
        service_name=service_name,
        metric_name="cpu_usage",
        metric_value=95.0,
    )


def test_trace_metric_same_service_within_five_seconds():
    timestamp = datetime.now(timezone.utc)

    trace = create_trace(
        "payment-service",
        timestamp,
    )

    metric = create_metric(
        "payment-service",
        timestamp + timedelta(seconds=3),
    )

    result = correlate_trace_metric(trace, metric)

    assert result is not None
    assert result.source_event_id == trace.event_id
    assert result.target_event_id == metric.event_id
    assert result.correlation_type == "service_time"
    assert result.strength == "MEDIUM"
    assert result.reason == "Same service within 5 seconds"


def test_trace_metric_different_service():
    timestamp = datetime.now(timezone.utc)

    trace = create_trace(
        "payment-service",
        timestamp,
    )

    metric = create_metric(
        "inventory-service",
        timestamp + timedelta(seconds=3),
    )

    result = correlate_trace_metric(trace, metric)

    assert result is None


def test_trace_metric_more_than_five_seconds_apart():
    timestamp = datetime.now(timezone.utc)

    trace = create_trace(
        "payment-service",
        timestamp,
    )

    metric = create_metric(
        "payment-service",
        timestamp + timedelta(seconds=6),
    )

    result = correlate_trace_metric(trace, metric)

    assert result is None


def test_trace_metric_exactly_five_seconds_apart():
    timestamp = datetime.now(timezone.utc)

    trace = create_trace(
        "payment-service",
        timestamp,
    )

    metric = create_metric(
        "payment-service",
        timestamp + timedelta(seconds=5),
    )

    result = correlate_trace_metric(trace, metric)

    assert result is not None
    assert result.strength == "MEDIUM"


def test_trace_metric_invalid_event_type():
    timestamp = datetime.now(timezone.utc)

    trace = create_trace(
        "payment-service",
        timestamp,
    )

    invalid_metric = NormalizedTelemetry(
        event_type="log",
        timestamp=timestamp,
        service_name="payment-service",
        message="CPU warning",
    )

    try:
        correlate_trace_metric(trace, invalid_metric)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Expected a metric event"