from backend.app.telemetry.correlation import (
    CorrelationResult,
    correlate_by_service_time,
    correlate_trace_log,
    correlate_trace_metric,
)
from backend.app.telemetry.normalized import NormalizedTelemetry


def correlate_events(
    events: list[NormalizedTelemetry],
) -> list[CorrelationResult]:
    """
    Correlate a collection of normalized telemetry events.

    Applies trace-log, trace-metric, and generic
    service-time correlation rules.
    """

    correlations: list[CorrelationResult] = []

    for index, source in enumerate(events):
        for target in events[index + 1:]:
            result: CorrelationResult | None = None

            # Trace → Log
            if (
                source.event_type == "trace"
                and target.event_type == "log"
            ):
                result = correlate_trace_log(source, target)

            elif (
                source.event_type == "log"
                and target.event_type == "trace"
            ):
                result = correlate_trace_log(target, source)

            # Trace → Metric
            elif (
                source.event_type == "trace"
                and target.event_type == "metric"
            ):
                result = correlate_trace_metric(source, target)

            elif (
                source.event_type == "metric"
                and target.event_type == "trace"
            ):
                result = correlate_trace_metric(target, source)

            # Generic service/time correlation
            else:
                result = correlate_by_service_time(
                    source,
                    target,
                )

            if result is not None:
                correlations.append(result)

    return correlations