from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class ServiceNode(BaseModel):
    """
    Represents a service node in the TraceRCA service topology.
    """

    service_name: str = Field(
        min_length=1,
        max_length=255,
    )

    first_seen: datetime
    last_seen: datetime

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        """Reject empty or whitespace-only service names."""

        if not value.strip():
            raise ValueError(
                "Service name cannot be empty or whitespace"
            )

        return value


class DependencyEdge(BaseModel):
    """
    Represents a dependency relationship between two services.
    """

    source_service: str = Field(
        min_length=1,
        max_length=255,
    )

    target_service: str = Field(
        min_length=1,
        max_length=255,
    )

    first_seen: datetime
    last_seen: datetime

    @field_validator("source_service", "target_service")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        """Reject empty or whitespace-only service names."""

        if not value.strip():
            raise ValueError(
                "Service name cannot be empty or whitespace"
            )

        return value

    @model_validator(mode="after")
    def validate_not_self_dependency(self) -> "DependencyEdge":
        """Ensure a service does not depend on itself."""

        if self.source_service == self.target_service:
            raise ValueError(
                "Source and target services cannot be the same"
            )

        return self


class TopologyResponse(BaseModel):
    """
    Represents the complete service topology retrieved from Neo4j.
    """

    services: list[ServiceNode]
    dependencies: list[DependencyEdge]