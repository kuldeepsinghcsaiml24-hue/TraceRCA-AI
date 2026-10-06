import pytest
from pydantic import ValidationError

from backend.app.telemetry.normalized import NormalizedTelemetry


def test_valid_trace_normalization():
    telemetry = NormalizedTelemetry(
        event_type="trace",
        timestamp="2026-10-05T20:00:00",
        service_name="payment-service",
        operation_name="process-payment",
        trace_id="trace-123",
        span_id="span-123",
        duration_ms=125.5,
        status="OK",
    )

    assert telemetry.event_type == "trace"
    assert telemetry.service_name == "payment-service"
    assert telemetry.operation_name == "process-payment"
    assert telemetry.duration_ms == 125.5
    assert telemetry.status == "OK"


def test_invalid_event_type():
    with pytest.raises(ValidationError):
        NormalizedTelemetry(
            event_type="invalid",
            timestamp="2026-10-05T20:00:00",
            service_name="test-service",
        )


def test_negative_duration_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedTelemetry(
            event_type="trace",
            timestamp="2026-10-05T20:00:00",
            service_name="test-service",
            duration_ms=-10,
        )


def test_empty_service_name_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedTelemetry(
            event_type="trace",
            timestamp="2026-10-05T20:00:00",
            service_name="   ",
        )


def test_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedTelemetry(
            event_type="trace",
            timestamp="2026-10-05T20:00:00",
            service_name="test-service",
            status="FAILED",
        )


def test_empty_message_is_rejected():
    with pytest.raises(ValidationError):
        NormalizedTelemetry(
            event_type="log",
            timestamp="2026-10-05T20:00:00",
            service_name="test-service",
            message="   ",
        )
def test_normalized_trace():
    telemetry = NormalizedTelemetry(
        event_type="trace",
        timestamp="2026-10-05T20:00:00",
        service_name="payment-service",
        operation_name="process-payment",
        trace_id="trace-123",
        span_id="span-123",
        parent_span_id="parent-123",
        duration_ms=125.5,
        status="ERROR",
        attributes={"http.method": "POST"},
    )

    assert telemetry.event_type == "trace"
    assert telemetry.operation_name == "process-payment"
    assert telemetry.duration_ms == 125.5
    assert telemetry.status == "ERROR"


def test_normalized_log():
    telemetry = NormalizedTelemetry(
        event_type="log",
        timestamp="2026-10-05T20:00:00",
        service_name="payment-service",
        message="Database connection failed",
        trace_id="trace-123",
        span_id="span-123",
        attributes={"level": "ERROR"},
    )

    assert telemetry.event_type == "log"
    assert telemetry.message == "Database connection failed"
    assert telemetry.trace_id == "trace-123"


def test_normalized_metric():
    telemetry = NormalizedTelemetry(
        event_type="metric",
        timestamp="2026-10-05T20:00:00",
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=87.4,
        attributes={"host": "server-01"},
    )

    assert telemetry.event_type == "metric"
    assert telemetry.metric_name == "cpu_usage"
    assert telemetry.metric_value == 87.4