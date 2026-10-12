from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import distinct, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from ...db.database import get_db
from ...db.models import TelemetryEvent
from ...telemetry.topology_service import topology_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview")
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
):
    """Return dashboard overview from persisted telemetry."""
    try:
        event_counts = await db.execute( 
            select(
                TelemetryEvent.event_type,
                func.count(TelemetryEvent.id),
            ).group_by(TelemetryEvent.event_type)
        )

        counts = {
            event_type: count
            for event_type, count in event_counts.all()
        }

        total_result = await db.execute(
            select(func.count(TelemetryEvent.id))
        )
        total_events = total_result.scalar_one()

        services_result = await db.execute(
            select(func.count(distinct(TelemetryEvent.service_name)))
        )
        service_count = services_result.scalar_one()

        errors_result = await db.execute(
            select(func.count(TelemetryEvent.id)).where(
                TelemetryEvent.event_type == "trace",
                func.upper(TelemetryEvent.status) == "ERROR",
            )
        )
        error_trace_count = errors_result.scalar_one()

        recent_result = await db.execute(
            select(TelemetryEvent)
            .order_by(TelemetryEvent.timestamp.desc())
            .limit(10)
        )
        recent_events = recent_result.scalars().all()

        return {
            "database_status": "connected",
            "total_events": total_events,
            "trace_count": counts.get("trace", 0),
            "log_count": counts.get("log", 0),
            "metric_count": counts.get("metric", 0),
            "service_count": service_count,
            "error_trace_count": error_trace_count,
            "recent_events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                    "service_name": event.service_name,
                    "trace_id": event.trace_id,
                    "operation_name": event.operation_name,
                    "status": event.status,
                    "duration_ms": event.duration_ms,
                    "message": event.message,
                    "metric_name": event.metric_name,
                    "metric_value": event.metric_value,
                }
                for event in recent_events
            ],
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard data is temporarily unavailable",
        )


@router.get("/services")
async def get_dashboard_services(
    db: AsyncSession = Depends(get_db),
):
    """Return service-level statistics from persisted telemetry."""
    from sqlalchemy import case

    try:
        result = await db.execute(
            select(
                TelemetryEvent.service_name,
                func.count(TelemetryEvent.id).label("event_count"),
                func.count(
                    case(
                        (
                            (TelemetryEvent.event_type == "trace")
                            & (
                                func.upper(TelemetryEvent.status)
                                == "ERROR"
                            ),
                            TelemetryEvent.id,
                        )
                    )
                ).label("error_trace_count"),
                func.avg(
                    case(
                        (
                            TelemetryEvent.event_type == "trace",
                            TelemetryEvent.duration_ms,
                        )
                    )
                ).label("average_duration_ms"),
                func.max(TelemetryEvent.timestamp).label("last_seen"),
            )
            .group_by(TelemetryEvent.service_name)
            .order_by(TelemetryEvent.service_name)
        )

        services = [
            {
                "service_name": row.service_name,
                "event_count": row.event_count,
                "error_trace_count": row.error_trace_count,
                "average_duration_ms": (
                    float(row.average_duration_ms)
                    if row.average_duration_ms is not None
                    else None
                ),
                "last_seen": row.last_seen,
            }
            for row in result.all()
        ]

        return {
            "service_count": len(services),
            "services": services,
        }

    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dashboard service data is temporarily unavailable",
        )


@router.get("/topology")
async def get_dashboard_topology():
    """Return the actual service topology stored in Neo4j."""
    try:
        topology = await topology_service.get_topology()
        return topology.model_dump(mode="json")

    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service topology is unavailable",
        )

