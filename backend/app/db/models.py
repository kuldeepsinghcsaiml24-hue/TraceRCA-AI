from datetime import datetime

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Service(Base):
    """Represent a monitored microservice."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="unknown",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TelemetryEvent(Base):
    """Represent a trace, log, or metric telemetry event."""

    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    service_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    span_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    parent_span_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    metric_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    metric_value: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    attributes: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )