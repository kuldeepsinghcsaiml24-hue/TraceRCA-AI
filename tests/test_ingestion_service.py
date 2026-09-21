import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import SQLAlchemyError

from backend.app.db.database import AsyncSessionLocal
from backend.app.telemetry.schemas import (
    LogIngestRequest,
    MetricIngestRequest,
    TraceIngestRequest,
)
from backend.app.telemetry.service import (
    ingest_log,
    ingest_metric,
    ingest_trace,
)


@pytest.mark.asyncio
async def test_ingest_trace_persists():
    async with AsyncSessionLocal() as db:
        data = TraceIngestRequest(
            trace_id="m57-test-trace",
            span_id="m57-test-span",
            service_name="test-service",
            operation_name="test-operation",
            timestamp=datetime.now(timezone.utc),
            duration_ms=25.5,
        )

        event = await ingest_trace(db, data)

        assert event.id is not None
        assert event.event_type == "trace"
        assert event.trace_id == "m57-test-trace"
        assert event.span_id == "m57-test-span"


@pytest.mark.asyncio
async def test_ingest_log_persists():
    async with AsyncSessionLocal() as db:
        data = LogIngestRequest(
            timestamp=datetime.now(timezone.utc),
            service_name="test-service",
            message="M5.7 test log",
            trace_id="m57-log-trace",
            span_id="m57-log-span",
        )

        event = await ingest_log(db, data)

        assert event.id is not None
        assert event.event_type == "log"
        assert event.message == "M5.7 test log"
        assert event.trace_id == "m57-log-trace"
        assert event.span_id == "m57-log-span"


@pytest.mark.asyncio
async def test_ingest_metric_persists():
    async with AsyncSessionLocal() as db:
        data = MetricIngestRequest(
            timestamp=datetime.now(timezone.utc),
            service_name="test-service",
            metric_name="m57_test_cpu",
            metric_value=75.5,
        )

        event = await ingest_metric(db, data)

        assert event.id is not None
        assert event.event_type == "metric"
        assert event.metric_name == "m57_test_cpu"
        assert event.metric_value == 75.5

@pytest.mark.asyncio
async def test_ingest_trace_rolls_back_on_database_error():
    db = MagicMock()
    db.commit = AsyncMock(side_effect=SQLAlchemyError("database failure"))
    db.rollback = AsyncMock()

    data = TraceIngestRequest(
        trace_id="m583-error-trace",
        span_id="m583-error-span",
        service_name="test-service",
        operation_name="test-operation",
        timestamp=datetime.now(timezone.utc),
        duration_ms=25.5,
    )

    with pytest.raises(SQLAlchemyError, match="database failure"):
        await ingest_trace(db, data)

    db.rollback.assert_awaited_once()