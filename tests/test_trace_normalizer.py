from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalizers import normalize_trace


def test_normalize_trace():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-123",
        span_id="span-123",
        parent_span_id="parent-123",
        operation_name="process-payment",
        duration_ms=245.5,
        status="ERROR",
        attributes={
            "http.method": "POST",
            "http.route": "/payments",
        },
    )

    normalized = normalize_trace(event)

    assert normalized.event_id == event.id
    assert normalized.event_type == "trace"
    assert normalized.timestamp == event.timestamp
    assert normalized.service_name == "payment-service"
    assert normalized.operation_name == "process-payment"
    assert normalized.trace_id == "trace-123"
    assert normalized.span_id == "span-123"
    assert normalized.parent_span_id == "parent-123"
    assert normalized.duration_ms == 245.5
    assert normalized.status == "ERROR"
    assert normalized.attributes == event.attributes


def test_normalize_trace_rejects_non_trace_event():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        message="Database connection failed",
        attributes={},
    )

    with pytest.raises(ValueError, match="Expected a trace telemetry event"):
        normalize_trace(event)

def test_normalize_trace_with_optional_fields_missing():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-456",
        span_id="span-456",
        parent_span_id=None,
        operation_name=None,
        duration_ms=None,
        status=None,
        attributes={},
    )

    normalized = normalize_trace(event)

    assert normalized.event_type == "trace"
    assert normalized.service_name == "payment-service"
    assert normalized.trace_id == "trace-456"
    assert normalized.span_id == "span-456"
    assert normalized.parent_span_id is None
    assert normalized.operation_name is None
    assert normalized.duration_ms is None
    assert normalized.status is None


def test_normalize_trace_with_none_attributes():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id="trace-789",
        span_id="span-789",
        attributes=None,
    )

    normalized = normalize_trace(event)

    assert normalized.attributes == {}