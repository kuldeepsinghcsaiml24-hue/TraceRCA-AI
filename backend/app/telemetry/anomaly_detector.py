from datetime import datetime

from backend.app.telemetry.anomaly import Anomaly


def detect_latency_anomaly(
    service_name: str,
    timestamp: datetime,
    observed_latency_ms: float,
    expected_latency_ms: float,
) -> Anomaly | None:
    """
    Detect a latency anomaly by comparing observed latency
    against the expected latency baseline.
    """

    if not service_name.strip():
        raise ValueError("Service name cannot be empty")

    if expected_latency_ms <= 0:
        raise ValueError(
            "Expected latency must be greater than zero"
        )

    if observed_latency_ms < 0:
        raise ValueError(
            "Observed latency cannot be negative"
        )

    deviation = abs(
        observed_latency_ms - expected_latency_ms
    ) / expected_latency_ms

    if deviation < 0.50:
        return None

    if deviation < 1.00:
        severity = "LOW"
    elif deviation < 2.00:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    percentage = deviation * 100

    return Anomaly(
        service_name=service_name,
        anomaly_type="LATENCY",
        timestamp=timestamp,
        observed_value=observed_latency_ms,
        expected_value=expected_latency_ms,
        severity=severity,
        description=(
            f"Latency deviated {percentage:.1f}% "
            f"from the expected baseline."
        ),
    )

def detect_error_rate_anomaly(
    service_name: str,
    timestamp: datetime,
    observed_error_rate: float,
    expected_error_rate: float,
) -> Anomaly | None:
    """
    Detect an error-rate anomaly by comparing the observed
    error rate against the expected error-rate baseline.
    """

    if not service_name.strip():
        raise ValueError("Service name cannot be empty")

    if not 0 <= observed_error_rate <= 100:
        raise ValueError(
            "Observed error rate must be between 0 and 100"
        )

    if not 0 <= expected_error_rate <= 100:
        raise ValueError(
            "Expected error rate must be between 0 and 100"
        )

    deviation = abs(
        observed_error_rate - expected_error_rate
    )

    if deviation < 5:
        return None

    if deviation < 10:
        severity = "LOW"
    elif deviation < 20:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    return Anomaly(
        service_name=service_name,
        anomaly_type="ERROR_RATE",
        timestamp=timestamp,
        observed_value=observed_error_rate,
        expected_value=expected_error_rate,
        severity=severity,
        description=(
            f"Error rate deviated {deviation:.1f} "
            "percentage points from the expected baseline."
        ),
    )

def detect_metric_anomaly(
    service_name: str,
    timestamp: datetime,
    observed_value: float,
    expected_value: float,
    metric_name: str,
) -> Anomaly | None:
    """
    Detect a metric anomaly by comparing the observed metric
    value against the expected baseline.
    """

    if not service_name.strip():
        raise ValueError("Service name cannot be empty")

    if not metric_name.strip():
        raise ValueError("Metric name cannot be empty")

    if expected_value == 0:
        raise ValueError(
            "Expected metric value cannot be zero"
        )

    deviation = abs(
        observed_value - expected_value
    ) / abs(expected_value)

    if deviation < 0.50:
        return None

    if deviation < 1.00:
        severity = "LOW"
    elif deviation < 2.00:
        severity = "MEDIUM"
    else:
        severity = "HIGH"

    percentage = deviation * 100

    return Anomaly(
        service_name=service_name,
        anomaly_type="METRIC",
        timestamp=timestamp,
        observed_value=observed_value,
        expected_value=expected_value,
        severity=severity,
        description=(
            f"Metric '{metric_name}' deviated "
            f"{percentage:.1f}% from the expected baseline."
        ),
    )