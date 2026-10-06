from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class NormalizedTelemetry(BaseModel):
    """
    Common internal representation for normalized telemetry.

    This schema provides a unified structure for traces, logs,
    and metrics before they enter the RCA pipeline.
    """

    event_id: UUID = Field(default_factory=uuid4)

    event_type: Literal["trace", "log", "metric"]

    timestamp: datetime

    service_name: str = Field(min_length=1, max_length=255)

    operation_name: str | None = Field(
        default=None,
        max_length=255,
    )

    trace_id: str | None = Field(
        default=None,
        max_length=255,
    )

    span_id: str | None = Field(
        default=None,
        max_length=255,
    )

    parent_span_id: str | None = Field(
        default=None,
        max_length=255,
    )

    duration_ms: float | None = Field(
        default=None,
        ge=0,
    )

    status: Literal["UNSET", "OK", "ERROR"] | None = None

    message: str | None = Field(
        default=None,
        max_length=10000,
    )

    metric_name: str | None = Field(
        default=None,
        max_length=255,
    )

    metric_value: float | None = None

    attributes: dict[str, Any] = Field(
        default_factory=dict,
    )

    @field_validator(
        "service_name",
        "operation_name",
        "trace_id",
        "span_id",
        "parent_span_id",
        "message",
        "metric_name",
        mode="before",
    )
    @classmethod
    def validate_non_empty_string(cls, value: Any) -> Any:
        """Reject empty or whitespace-only strings."""
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value cannot be empty or whitespace")

        return value