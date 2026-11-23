from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.telemetry.anomaly import Anomaly
from backend.app.telemetry.normalized import NormalizedTelemetry
from backend.app.telemetry.topology import TopologyResponse


TemporalPosition = Literal["BEFORE", "AT", "AFTER", "UNCLASSIFIED"]
TemporalServiceRole = Literal[
    "INCIDENT_SERVICE",
    "UPSTREAM_DEPENDENCY",
    "DOWNSTREAM_SERVICE",
    "OTHER",
    "UNKNOWN",
]


class TemporalEvent(BaseModel):
    """A telemetry event positioned on an incident timeline."""

    event_id: int | str
    event_type: Literal["trace", "log", "metric"]
    timestamp: datetime
    service_name: str
    position: TemporalPosition
    seconds_from_anomaly: float | None = None
    service_role: TemporalServiceRole = "UNKNOWN"


class TemporalAnalysisResult(BaseModel):
    """Chronological telemetry and its relationship to an anomaly."""

    anomaly_timestamp: datetime | None = None
    events: list[TemporalEvent] = Field(default_factory=list)
    events_before_anomaly: list[int | str] = Field(default_factory=list)
    events_at_anomaly: list[int | str] = Field(default_factory=list)
    events_after_anomaly: list[int | str] = Field(default_factory=list)
    unclassified_events: list[int | str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def analyze_temporal_events(
    events: list[NormalizedTelemetry],
    anomaly: Anomaly | None = None,
    *,
    incident_service_name: str | None = None,
    topology: TopologyResponse | None = None,
    upstream_dependencies: list[str] | None = None,
    downstream_impact: list[str] | None = None,
) -> TemporalAnalysisResult:
    """
    Sort events chronologically and classify them relative to an anomaly.

    Service roles use the incident context and supplied topology analysis.
    Temporal ordering and topology do not independently establish causation.
    """
    ordered_events = sorted(
        events,
        key=lambda event: (event.timestamp, str(event.event_id)),
    )

    anomaly_timestamp = anomaly.timestamp if anomaly else None
    before: list[int | str] = []
    at: list[int | str] = []
    after: list[int | str] = []
    unclassified: list[int | str] = []

    if topology is None:
        service_roles_known = False
        upstream = set()
        downstream = set()
    else:
        service_roles_known = True
        upstream = set(upstream_dependencies or [])
        downstream = set(downstream_impact or [])

    timeline: list[TemporalEvent] = []

    for event in ordered_events:
        position: TemporalPosition = "UNCLASSIFIED"
        seconds_from_anomaly = None

        if anomaly_timestamp is not None:
            seconds_from_anomaly = (
                event.timestamp - anomaly_timestamp
            ).total_seconds()

            if event.timestamp < anomaly_timestamp:
                position = "BEFORE"
                before.append(event.event_id)
            elif event.timestamp > anomaly_timestamp:
                position = "AFTER"
                after.append(event.event_id)
            else:
                position = "AT"
                at.append(event.event_id)
        else:
            unclassified.append(event.event_id)

        if not service_roles_known:
            service_role: TemporalServiceRole = "UNKNOWN"
        elif event.service_name == incident_service_name:
            service_role = "INCIDENT_SERVICE"
        elif event.service_name in upstream:
            service_role = "UPSTREAM_DEPENDENCY"
        elif event.service_name in downstream:
            service_role = "DOWNSTREAM_SERVICE"
        else:
            service_role = "OTHER"

        timeline.append(
            TemporalEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                service_name=event.service_name,
                position=position,
                seconds_from_anomaly=seconds_from_anomaly,
                service_role=service_role,
            )
        )

    limitations = [
        "Temporal ordering does not establish causation.",
        "Topology relationships indicate dependencies or potential impact, "
        "not proof of the root cause.",
    ]

    if anomaly_timestamp is None:
        limitations.append(
            "No anomaly timestamp was supplied; events are ordered "
            "chronologically but are not classified relative to symptom onset."
        )

    if not service_roles_known:
        limitations.append(
            "Topology was unavailable; service roles could not be determined."
        )

    return TemporalAnalysisResult(
        anomaly_timestamp=anomaly_timestamp,
        events=timeline,
        events_before_anomaly=before,
        events_at_anomaly=at,
        events_after_anomaly=after,
        unclassified_events=unclassified,
        limitations=limitations,
    )
