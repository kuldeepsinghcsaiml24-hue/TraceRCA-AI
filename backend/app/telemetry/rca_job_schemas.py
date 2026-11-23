from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .incident import IncidentContext
from .rca_api_schemas import RCAAnalysisResponse


RCAJobStatus = Literal[
    "QUEUED",
    "RUNNING",
    "COMPLETED",
    "FAILED",
]


class RCAJobSubmissionResponse(BaseModel):
    """Acknowledge an accepted asynchronous RCA job."""

    job_id: UUID = Field(default_factory=uuid4)
    incident_id: UUID
    status: Literal["QUEUED"] = "QUEUED"
    status_url: str
    result_url: str


class RCAJobStatusResponse(BaseModel):
    """Expose the lifecycle and optional result of an RCA job."""

    model_config = ConfigDict(use_enum_values=True)

    job_id: UUID
    incident_id: UUID
    status: RCAJobStatus
    created_at: datetime
    updated_at: datetime
    result: RCAAnalysisResponse | None = None
    error: str | None = None


class RCAJobPayload(BaseModel):
    """Represent the validated input persisted for worker execution."""

    job_id: UUID = Field(default_factory=uuid4)
    incident: IncidentContext
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
