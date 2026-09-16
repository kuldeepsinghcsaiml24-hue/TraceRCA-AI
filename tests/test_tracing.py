from opentelemetry import trace

from backend.app.telemetry.tracing import (
    configure_tracing,
    create_telemetry_span,
)


def test_tracer_can_create_span() -> None:
    """Verify that OpenTelemetry can create a valid span."""

    configure_tracing("tracerca-test")

    tracer = trace.get_tracer("tracerca-test")

    with tracer.start_as_current_span("test-operation") as span:
        assert span is not None
        assert span.get_span_context().is_valid


def test_create_telemetry_span() -> None:
    """Verify that an OpenTelemetry span becomes a TelemetrySpan model."""

    configure_tracing("tracerca-test")

    tracer = trace.get_tracer("tracerca-test")

    telemetry_span = create_telemetry_span(
        tracer=tracer,
        service_name="payment-service",
        operation_name="process-payment",
    )

    assert len(telemetry_span.trace_id) == 32
    assert len(telemetry_span.span_id) == 16
    assert telemetry_span.service_name == "payment-service"
    assert telemetry_span.operation_name == "process-payment"
    assert telemetry_span.timestamp is not None
    assert telemetry_span.duration_ms >= 0
    assert telemetry_span.status == "UNSET"
    assert telemetry_span.attributes == {}