from datetime import datetime, timezone
from uuid import uuid4

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalizers import normalize_event


def test_trace_normalization_pipeline():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="order-service",
        operation_name="create-order",
        trace_id="trace-001",
        span_id="span-001",
        parent_span_id="span-000",
        duration_ms=180.5,
        status="OK",
        attributes={"http.method": "POST"},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "trace"
    assert normalized.service_name == "order-service"
    assert normalized.operation_name == "create-order"
    assert normalized.trace_id == "trace-001"
    assert normalized.span_id == "span-001"
    assert normalized.parent_span_id == "span-000"
    assert normalized.duration_ms == 180.5
    assert normalized.status == "OK"
    assert normalized.attributes == {"http.method": "POST"}


def test_log_normalization_pipeline():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="order-service",
        trace_id="trace-001",
        span_id="span-001",
        message="Order database lookup failed",
        attributes={"level": "ERROR"},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "log"
    assert normalized.service_name == "order-service"
    assert normalized.trace_id == "trace-001"
    assert normalized.span_id == "span-001"
    assert normalized.message == "Order database lookup failed"
    assert normalized.attributes == {"level": "ERROR"}


def test_metric_normalization_pipeline():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="order-service",
        metric_name="request_latency",
        metric_value=245.7,
        attributes={"unit": "ms"},
    )

    normalized = normalize_event(event)

    assert normalized.event_type == "metric"
    assert normalized.service_name == "order-service"
    assert normalized.metric_name == "request_latency"
    assert normalized.metric_value == 245.7
    assert normalized.attributes == {"unit": "ms"}