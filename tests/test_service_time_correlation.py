from datetime import datetime, timedelta, timezone

from backend.app.telemetry.correlation import correlate_by_service_time
from backend.app.telemetry.normalized import NormalizedTelemetry


def create_event(
    event_type: str,
    service_name: str,
    timestamp: datetime,
):
    if event_type == "trace":
        return NormalizedTelemetry(
            event_type="trace",
            timestamp=timestamp,
            service_name=service_name,
            trace_id="trace-123",
            operation_name="process-payment",
            status="ERROR",
        )

    if event_type == "log":
        return NormalizedTelemetry(
            event_type="log",
            timestamp=timestamp,
            service_name=service_name,
            message="Database timeout",
        )

    return NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp,
        service_name=service_name,
        metric_name="cpu_usage",
        metric_value=95.0,
    )


def test_same_service_within_five_seconds():
    timestamp = datetime.now(timezone.utc)

    source = create_event(
        "trace",
        "payment-service",
        timestamp,
    )

    target = create_event(
        "log",
        "payment-service",
        timestamp + timedelta(seconds=3),
    )

    result = correlate_by_service_time(source, target)

    assert result is not None
    assert result.source_event_id == source.event_id
    assert result.target_event_id == target.event_id
    assert result.correlation_type == "service_time"
    assert result.strength == "MEDIUM"
    assert result.reason == "Same service within 5 seconds"


def test_different_services():
    timestamp = datetime.now(timezone.utc)

    source = create_event(
        "trace",
        "payment-service",
        timestamp,
    )

    target = create_event(
        "log",
        "inventory-service",
        timestamp + timedelta(seconds=2),
    )

    result = correlate_by_service_time(source, target)

    assert result is None


def test_more_than_five_seconds():
    timestamp = datetime.now(timezone.utc)

    source = create_event(
        "trace",
        "payment-service",
        timestamp,
    )

    target = create_event(
        "metric",
        "payment-service",
        timestamp + timedelta(seconds=6),
    )

    result = correlate_by_service_time(source, target)

    assert result is None


def test_exactly_five_seconds():
    timestamp = datetime.now(timezone.utc)

    source = create_event(
        "log",
        "payment-service",
        timestamp,
    )

    target = create_event(
        "metric",
        "payment-service",
        timestamp + timedelta(seconds=5),
    )

    result = correlate_by_service_time(source, target)

    assert result is not None
    assert result.strength == "MEDIUM"


def test_events_can_be_any_telemetry_types():
    timestamp = datetime.now(timezone.utc)

    source = create_event(
        "metric",
        "payment-service",
        timestamp,
    )

    target = create_event(
        "log",
        "payment-service",
        timestamp + timedelta(seconds=1),
    )

    result = correlate_by_service_time(source, target)

    assert result is not None
    assert result.correlation_type == "service_time"