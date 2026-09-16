from datetime import datetime, timezone

from backend.app.telemetry.models import SpanStatus, TelemetrySpan


def test_telemetry_span_model() -> None:
    """Verify that a telemetry span can be created."""

    span = TelemetrySpan(
        trace_id="abc123",
        span_id="span001",
        parent_span_id=None,
        service_name="payment-service",
        operation_name="process-payment",
        timestamp=datetime.now(timezone.utc),
        duration_ms=125.5,
        status=SpanStatus.OK,
        attributes={
            "http.method": "POST",
            "http.status_code": 200,
        },
    )

    assert span.trace_id == "abc123"
    assert span.span_id == "span001"
    assert span.service_name == "payment-service"
    assert span.operation_name == "process-payment"
    assert span.duration_ms == 125.5
    assert span.status == "OK"
    assert span.attributes["http.method"] == "POST"