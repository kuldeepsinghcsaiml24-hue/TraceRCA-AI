from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from .models import TelemetrySpan


def configure_tracing(service_name: str) -> None:
    """Configure the OpenTelemetry tracer provider."""

    resource = Resource.create(
        {
            "service.name": service_name,
        }
    )

    provider = TracerProvider(resource=resource)

    trace.set_tracer_provider(provider)


def get_tracer(name: str = "tracerca") -> trace.Tracer:
    """Return an OpenTelemetry tracer."""

    return trace.get_tracer(name)


def create_telemetry_span(
    tracer: trace.Tracer,
    service_name: str,
    operation_name: str,
) -> TelemetrySpan:
    """Create a span and convert its context into a telemetry model."""

    with tracer.start_as_current_span(operation_name) as span:
        span_context = span.get_span_context()

        return TelemetrySpan(
            trace_id=format(span_context.trace_id, "032x"),
            span_id=format(span_context.span_id, "016x"),
            parent_span_id=None,
            service_name=service_name,
            operation_name=operation_name,
            timestamp=datetime.now(timezone.utc),
            duration_ms=0.0,
            status="UNSET",
            attributes={},
        )