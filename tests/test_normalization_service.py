from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalizers import normalize_event


def test_normalize_event_routes_trace():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        operation_name="process-payment",
        trace_id="trace-123",
        span_id="span-123",
        duration_ms=125.5,
        status="OK",
        attributes={},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "trace"
    assert normalized.operation_name == "process-payment"
    assert normalized.duration_ms == 125.5
    assert normalized.trace_id == "trace-123"


def test_normalize_event_routes_log():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-123",
        span_id="span-123",
        message="Database connection failed",
        attributes={},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "log"
    assert normalized.message == "Database connection failed"
    assert normalized.trace_id == "trace-123"


def test_normalize_event_routes_metric():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.4,
        attributes={},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "metric"
    assert normalized.metric_name == "cpu_usage"
    assert normalized.metric_value == 95.4


def test_normalize_event_rejects_unsupported_type():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="unknown",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        attributes={},
    )

    with pytest.raises(
        ValueError,
        match="Unsupported telemetry event type: unknown",
    ):
        normalize_event(event)