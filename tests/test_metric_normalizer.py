from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.db.models import TelemetryEvent
from backend.app.telemetry.normalizers import normalize_metric


def test_normalize_metric():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.4,
        attributes={
            "unit": "percent",
            "host": "server-01",
        },
    )

    normalized = normalize_metric(event)

    assert normalized.event_id == event.id
    assert normalized.event_type == "metric"
    assert normalized.timestamp == event.timestamp
    assert normalized.service_name == "payment-service"
    assert normalized.metric_name == "cpu_usage"
    assert normalized.metric_value == 95.4
    assert normalized.attributes == event.attributes


def test_normalize_metric_rejects_non_metric_event():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        message="CPU usage is high",
        attributes={},
    )

    with pytest.raises(ValueError, match="Expected a metric telemetry event"):
        normalize_metric(event)

def test_normalize_metric_with_none_attributes():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        metric_name="memory_usage",
        metric_value=72.5,
        attributes=None,
    )

    normalized = normalize_metric(event)

    assert normalized.attributes == {}


def test_normalize_metric_with_zero_value():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        metric_name="error_rate",
        metric_value=0.0,
        attributes={},
    )

    normalized = normalize_metric(event)

    assert normalized.metric_value == 0.0


def test_normalize_metric_with_negative_value():
    event = TelemetryEvent(
        id=uuid4(),
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="temperature-service",
        metric_name="temperature_change",
        metric_value=-5.5,
        attributes={},
    )

    normalized = normalize_metric(event)

    assert normalized.metric_value == -5.5