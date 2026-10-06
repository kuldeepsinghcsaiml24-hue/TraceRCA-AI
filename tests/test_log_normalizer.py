from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalizers import normalize_log


def test_normalize_log():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-123",
        span_id="span-123",
        message="Database connection failed",
        attributes={
            "level": "ERROR",
            "component": "database",
        },
    )

    normalized = normalize_log(event)

    assert normalized.event_id == event.id
    assert normalized.event_type == "log"
    assert normalized.timestamp == event.timestamp
    assert normalized.service_name == "payment-service"
    assert normalized.trace_id == "trace-123"
    assert normalized.span_id == "span-123"
    assert normalized.message == "Database connection failed"
    assert normalized.attributes == event.attributes


def test_normalize_log_rejects_non_log_event():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-123",
        span_id="span-123",
        operation_name="process-payment",
        duration_ms=125.5,
        status="OK",
        attributes={},
    )

    with pytest.raises(ValueError, match="Expected a log telemetry event"):
        normalize_log(event)

def test_normalize_log_without_trace_id():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        span_id="span-123",
        message="Payment processing started",
        attributes={},
    )

    normalized = normalize_log(event)

    assert normalized.trace_id is None
    assert normalized.span_id == "span-123"
    assert normalized.message == "Payment processing started"


def test_normalize_log_without_span_id():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-123",
        message="Payment processing started",
        attributes={},
    )

    normalized = normalize_log(event)

    assert normalized.trace_id == "trace-123"
    assert normalized.span_id is None
    assert normalized.message == "Payment processing started"


def test_normalize_log_with_none_attributes():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        message="Database connection failed",
        attributes=None,
    )

    normalized = normalize_log(event)

    assert normalized.attributes == {}