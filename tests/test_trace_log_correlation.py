from datetime import datetime, timezone

from backend.app.telemetry.correlation import correlate_trace_log
from backend.app.telemetry.normalized import NormalizedTelemetry


def create_trace(trace_id: str | None):
    return NormalizedTelemetry(
        event_type="trace",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id=trace_id,
        operation_name="process-payment",
        status="ERROR",
    )


def create_log(trace_id: str | None):
    return NormalizedTelemetry(
        event_type="log",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        trace_id=trace_id,
        message="Database connection timeout",
    )


def test_trace_log_same_trace_id():
    trace_id = "trace-123"

    trace = create_trace(trace_id)
    log = create_log(trace_id)

    result = correlate_trace_log(trace, log)

    assert result is not None
    assert result.source_event_id == trace.event_id
    assert result.target_event_id == log.event_id
    assert result.correlation_type == "trace_id"
    assert result.strength == "STRONG"
    assert result.reason == "Same trace_id"


def test_trace_log_different_trace_id():
    trace = create_trace("trace-123")
    log = create_log("trace-456")

    result = correlate_trace_log(trace, log)

    assert result is None


def test_trace_log_missing_trace_id():
    trace = create_trace(None)
    log = create_log(None)

    result = correlate_trace_log(trace, log)

    assert result is None


def test_trace_log_one_missing_trace_id():
    trace = create_trace("trace-123")
    log = create_log(None)

    result = correlate_trace_log(trace, log)

    assert result is None


def test_trace_log_invalid_event_types():
    trace = create_trace("trace-123")

    invalid_log = NormalizedTelemetry(
        event_type="metric",
        timestamp=datetime.now(timezone.utc),
        service_name="payment-service",
        metric_name="cpu_usage",
        metric_value=95.0,
    )

    try:
        correlate_trace_log(trace, invalid_log)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Expected a log event"


def test_same_trace_and_span_id_is_very_strong():
    trace = create_trace("trace-123")
    trace.span_id = "span-456"

    log = create_log("trace-123")
    log.span_id = "span-456"

    result = correlate_trace_log(trace, log)

    assert result is not None
    assert result.correlation_type == "span_id"
    assert result.strength == "VERY_STRONG"
    assert result.reason == "Same trace_id and span_id"


def test_same_trace_different_span_id_is_strong():
    trace = create_trace("trace-123")
    trace.span_id = "span-456"

    log = create_log("trace-123")
    log.span_id = "span-789"

    result = correlate_trace_log(trace, log)

    assert result is not None
    assert result.correlation_type == "trace_id"
    assert result.strength == "STRONG"


def test_same_trace_missing_span_id_is_strong():
    trace = create_trace("trace-123")
    trace.span_id = "span-456"

    log = create_log("trace-123")
    log.span_id = None

    result = correlate_trace_log(trace, log)

    assert result is not None
    assert result.correlation_type == "trace_id"
    assert result.strength == "STRONG"