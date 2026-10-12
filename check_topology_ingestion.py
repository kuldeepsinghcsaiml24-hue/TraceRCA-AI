import asyncio
import traceback

from sqlalchemy import select

from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import TelemetryEvent
from backend.app.db.neo4j import neo4j_connection
from backend.app.telemetry.normalizers import normalize_event
from backend.app.telemetry.topology_builder import topology_builder
from backend.app.telemetry.topology_service import topology_service


TRACE_ID = "tracerca-topology-test-20261012"


async def main():
    try:
        await neo4j_connection.connect()
        print("1. Neo4j connected.")

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(TelemetryEvent)
                .where(
                    TelemetryEvent.trace_id == TRACE_ID,
                    TelemetryEvent.event_type == "trace",
                )
                .order_by(TelemetryEvent.id)
            )
            events = result.scalars().all()

            print("2. Matching PostgreSQL events:", len(events))

            for event in events:
                print(
                    f"   ID={event.id}, "
                    f"service={event.service_name}, "
                    f"span={event.span_id}, "
                    f"parent={event.parent_span_id}"
                )

            normalized_events = [
                normalize_event(event) for event in events
            ]

            for event in normalized_events:
                await topology_builder.process_event(event)

            spans_by_id = {
                event.span_id: event
                for event in normalized_events
                if event.span_id
            }

            for child in normalized_events:
                if not child.parent_span_id:
                    continue

                parent = spans_by_id.get(child.parent_span_id)

                if parent is not None:
                    await topology_builder.create_dependency_from_trace(
                        parent,
                        child,
                    )

        print("3. Direct topology processing completed.")

        topology = await topology_service.get_topology()

        print("4. Services:", len(topology.services))
        for service in topology.services:
            print("   -", service.service_name)

        print("5. Dependencies:", len(topology.dependencies))
        for dependency in topology.dependencies:
            print(
                f"   - {dependency.source_service}"
                f" -> {dependency.target_service}"
            )

    except Exception:
        traceback.print_exc()

    finally:
        await neo4j_connection.close()


if __name__ == "__main__":
    asyncio.run(main())
