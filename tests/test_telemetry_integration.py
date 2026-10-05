from opentelemetry import trace
import pytest

from backend.app.db.database import AsyncSessionLocal
from backend.app.telemetry.schemas import TraceIngestRequest
from backend.app.telemetry.service import ingest_trace
from backend.app.telemetry.tracing import (
    configure_tracing,
    create_telemetry_span,
)


@pytest.mark.asyncio
async def test_opentelemetry_trace_flows_to_database():
    """Verify that an OpenTelemetry span can be ingested and persisted."""

    configure_tracing("tracerca-integration-test")

    tracer = trace.get_tracer("tracerca-integration-test")

    telemetry_span = create_telemetry_span(
        tracer=tracer,
        service_name="payment-service",
        operation_name="process-payment",
    )

    data = TraceIngestRequest(
        trace_id=telemetry_span.trace_id,
        span_id=telemetry_span.span_id,
        parent_span_id=telemetry_span.parent_span_id,
        service_name=telemetry_span.service_name,
        operation_name=telemetry_span.operation_name,
        timestamp=telemetry_span.timestamp,
        duration_ms=telemetry_span.duration_ms,
        status=telemetry_span.status,
        attributes=telemetry_span.attributes,
    )

    async with AsyncSessionLocal() as db:
        event = await ingest_trace(db, data)

        assert event.id is not None
        assert event.event_type == "trace"
        assert event.trace_id == telemetry_span.trace_id
        assert event.span_id == telemetry_span.span_id
        assert event.service_name == "payment-service"