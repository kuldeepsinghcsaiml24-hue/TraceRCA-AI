import logging
from datetime import datetime, timezone

from opentelemetry.proto.collector.trace.v1 import (
    trace_service_pb2,
    trace_service_pb2_grpc,
)
from opentelemetry.proto.common.v1.common_pb2 import AnyValue

from ..db.database import AsyncSessionLocal
from .service import ingest_trace

logger = logging.getLogger(__name__)


def _attribute_value(value: AnyValue):
    """Convert an OTLP AnyValue into a JSON-compatible Python value."""
    kind = value.WhichOneof("value")

    if kind is None:
        return None
    if kind == "string_value":
        return value.string_value
    if kind == "bool_value":
        return value.bool_value
    if kind == "int_value":
        return value.int_value
    if kind == "double_value":
        return value.double_value
    if kind == "bytes_value":
        return value.bytes_value.hex()
    if kind == "array_value":
        return [_attribute_value(item) for item in value.array_value.values]
    if kind == "kvlist_value":
        return {
            item.key: _attribute_value(item.value)
            for item in value.kvlist_value.values
        }

    return None


def _attributes_to_dict(attributes) -> dict:
    """Convert OTLP key-value attributes into a dictionary."""
    return {
        item.key: _attribute_value(item.value)
        for item in attributes
    }


def _status_to_string(code: int) -> str:
    """Map OTLP span status to TraceRCA's supported status values."""
    if code == 2:
        return "ERROR"
    if code == 1:
        return "OK"
    return "UNSET"


def _timestamp_from_unix_nanos(value: int) -> datetime:
    """Convert Unix nanoseconds into a timezone-aware UTC datetime."""
    seconds, nanos = divmod(value, 1_000_000_000)
    return datetime.fromtimestamp(
        seconds + nanos / 1_000_000_000,
        tz=timezone.utc,
    )


def _span_to_ingest_request(span, service_name: str):
    """Convert an OTLP span to TraceRCA's existing ingestion schema."""
    from .schemas import TraceIngestRequest

    if not span.trace_id or not span.span_id:
        raise ValueError("Span is missing its trace ID or span ID")

    if not span.name.strip():
        raise ValueError("Span name cannot be empty")

    if not service_name.strip():
        raise ValueError("Resource is missing service.name")

    duration_ns = span.end_time_unix_nano - span.start_time_unix_nano
    if span.start_time_unix_nano <= 0 or span.end_time_unix_nano <= 0:
        raise ValueError("Span start and end timestamps must be positive")

    if duration_ns < 0:
        raise ValueError("Span end time precedes start time")

    start_time = _timestamp_from_unix_nanos(span.start_time_unix_nano)
    duration_ms = duration_ns / 1_000_000

    attributes = _attributes_to_dict(span.attributes)
    attributes["otel.span_kind"] = span.kind

    if span.status.message:
        attributes["otel.status_message"] = span.status.message

    if span.events:
        attributes["otel.events"] = [
            {
                "name": event.name,
                "timestamp": event.time_unix_nano,
                "attributes": _attributes_to_dict(event.attributes),
            }
            for event in span.events
        ]

    if span.links:
        attributes["otel.links"] = [
            {
                "trace_id": link.trace_id.hex(),
                "span_id": link.span_id.hex(),
                "attributes": _attributes_to_dict(link.attributes),
            }
            for link in span.links
        ]

    return TraceIngestRequest(
        trace_id=span.trace_id.hex(),
        span_id=span.span_id.hex(),
        parent_span_id=span.parent_span_id.hex() or None,
        service_name=service_name,
        operation_name=span.name,
        timestamp=start_time,
        duration_ms=duration_ms,
        status=_status_to_string(span.status.code),
        attributes=attributes,
    )


class OtlpTraceReceiver(
    trace_service_pb2_grpc.TraceServiceServicer
):
    """Receive OTLP spans and persist them through TraceRCA's ingestion service."""

    async def Export(self, request, context):
        accepted = 0
        rejected = 0

        for resource_spans in request.resource_spans:
            resource_attributes = _attributes_to_dict(
                resource_spans.resource.attributes
            )
            service_name = resource_attributes.get("service.name", "")

            for scope_spans in resource_spans.scope_spans:
                for span in scope_spans.spans:
                    try:
                        ingest_request = _span_to_ingest_request(
                            span,
                            service_name,
                        )

                        async with AsyncSessionLocal() as db:
                            await ingest_trace(db, ingest_request)

                        accepted += 1

                    except Exception:
                        rejected += 1
                        logger.exception(
                            "Failed to ingest OTLP span %s",
                            span.name,
                        )

        response = trace_service_pb2.ExportTraceServiceResponse()
        if rejected:
            response.partial_success.rejected_spans = rejected
            response.partial_success.error_message = (
                f"Rejected or failed to persist {rejected} span(s)"
            )

        logger.info(
            "OTLP export processed: accepted=%d rejected=%d",
            accepted,
            rejected,
        )
        return response
