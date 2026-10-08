from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Anomaly(BaseModel):
    """
    Represents an anomaly detected in normalized telemetry.
    """

    anomaly_id: UUID = Field(
        default_factory=uuid4
    )

    service_name: str = Field(
        min_length=1,
        max_length=255,
    )

    anomaly_type: Literal[
        "LATENCY",
        "ERROR_RATE",
        "METRIC",
    ]

    timestamp: datetime

    observed_value: float

    expected_value: float

    severity: Literal[
        "LOW",
        "MEDIUM",
        "HIGH",
    ]

    description: str = Field(
        min_length=1,
        max_length=1000,
    )