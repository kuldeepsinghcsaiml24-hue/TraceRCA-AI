from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TraceIngestRequest(BaseModel):
    """Incoming distributed trace/span telemetry."""

    trace_id: str = Field(min_length=1, max_length=255)
    span_id: str = Field(min_length=1, max_length=255)
    parent_span_id: str | None = Field(default=None, max_length=255)

    service_name: str = Field(min_length=1, max_length=255)
    operation_name: str = Field(min_length=1, max_length=255)

    timestamp: datetime
    duration_ms: float = Field(ge=0)

    status: Literal["UNSET", "OK", "ERROR"] = "UNSET"

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "trace_id",
        "span_id",
        "service_name",
        "operation_name",
        mode="before",
    )
    @classmethod
    def validate_non_empty_string(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value cannot be empty or whitespace")
        return value


class LogIngestRequest(BaseModel):
    """Incoming log telemetry."""

    timestamp: datetime

    service_name: str = Field(min_length=1, max_length=255)

    message: str = Field(min_length=1, max_length=10000)

    trace_id: str | None = Field(default=None, max_length=255)
    span_id: str | None = Field(default=None, max_length=255)

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("service_name", "message", mode="before")
    @classmethod
    def validate_non_empty_string(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value cannot be empty or whitespace")
        return value


class MetricIngestRequest(BaseModel):
    """Incoming metric telemetry."""

    timestamp: datetime

    service_name: str = Field(min_length=1, max_length=255)

    metric_name: str = Field(min_length=1, max_length=255)
    metric_value: float

    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("service_name", "metric_name", mode="before")
    @classmethod
    def validate_non_empty_string(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Value cannot be empty or whitespace")
        return value