from datetime import datetime

from pydantic import BaseModel, Field


class SpanStatus(str):
    """Supported span status values."""

    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


class TelemetrySpan(BaseModel):
    """Represent the core information of an OpenTelemetry span."""

    trace_id: str = Field(min_length=1)
    span_id: str = Field(min_length=1)
    parent_span_id: str | None = None

    service_name: str = Field(min_length=1)
    operation_name: str = Field(min_length=1)

    timestamp: datetime
    duration_ms: float = Field(ge=0)

    status: str = SpanStatus.UNSET

    attributes: dict[str, object] = Field(default_factory=dict)