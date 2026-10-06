from datetime import datetime, timedelta, timezone

from backend.app.telemetry.correlation_service import correlate_events
from backend.app.telemetry.normalized import NormalizedTelemetry


def test_unified_trace_log_correlation():
    timestamp = datetime.now(timezone.utc)

    trace = NormalizedTelemetry(
        event_type="trace",
        timestamp=timestamp,
        service_name="payment-service",
        trace_id="trace-123",
        operation_name="process-payment",
        status="ERROR",
    )

    log = NormalizedTelemetry(
        event_type="log",
        timestamp=timestamp + timedelta(seconds=1),
        service_name="payment-service",
        trace_id="trace-123",
        message="Database timeout",
    )

    results = correlate_events([trace, log])

    assert len(results) == 1
    assert results[0].correlation_type == "trace_id"
    assert results[0].strength == "STRONG"


def test_unified_trace_metric_correlation():
    timestamp = datetime.now(timezone.utc)

    trace = NormalizedTelemetry(
        event_type="trace",
        timestamp=timestamp,
        service_name="payment-service",
        trace_id="trace-123",
        operation_name="process-payment",
        status="ERROR",
    )

    metric = NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp + timedelta(seconds=3),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.0,
    )

    results = correlate_events([trace, metric])

    assert len(results) == 1
    assert results[0].correlation_type == "service_time"
    assert results[0].strength == "MEDIUM"


def test_unified_generic_service_time_correlation():
    timestamp = datetime.now(timezone.utc)

    log = NormalizedTelemetry(
        event_type="log",
        timestamp=timestamp,
        service_name="payment-service",
        message="Database timeout",
    )

    metric = NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp + timedelta(seconds=2),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.0,
    )

    results = correlate_events([log, metric])

    assert len(results) == 1
    assert results[0].correlation_type == "service_time"
    assert results[0].strength == "MEDIUM"


def test_unified_no_correlation_for_unrelated_events():
    timestamp = datetime.now(timezone.utc)

    trace = NormalizedTelemetry(
        event_type="trace",
        timestamp=timestamp,
        service_name="payment-service",
        trace_id="trace-123",
        operation_name="process-payment",
        status="ERROR",
    )

    metric = NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp + timedelta(seconds=10),
        service_name="inventory-service",
        metric_name="cpu_usage",
        metric_value=95.0,
    )

    results = correlate_events([trace, metric])

    assert results == []


def test_unified_multiple_correlations():
    timestamp = datetime.now(timezone.utc)

    trace = NormalizedTelemetry(
        event_type="trace",
        timestamp=timestamp,
        service_name="payment-service",
        trace_id="trace-123",
        operation_name="process-payment",
        status="ERROR",
    )

    log = NormalizedTelemetry(
        event_type="log",
        timestamp=timestamp + timedelta(seconds=1),
        service_name="payment-service",
        trace_id="trace-123",
        message="Database timeout",
    )

    metric = NormalizedTelemetry(
        event_type="metric",
        timestamp=timestamp + timedelta(seconds=3),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.0,
    )

    results = correlate_events([trace, log, metric])

    assert len(results) == 3

    correlation_types = {
        result.correlation_type
        for result in results
    }

    assert "trace_id" in correlation_types
    assert "service_time" in correlation_types