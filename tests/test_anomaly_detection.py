from datetime import datetime, timezone

import pytest

from backend.app.telemetry.anomaly_detector import (
    detect_error_rate_anomaly,
    detect_latency_anomaly,
    detect_metric_anomaly,
)
from backend.app.telemetry.anomaly_service import (
    anomaly_detection_service,
)


TIMESTAMP = datetime.now(timezone.utc)


# ---------------------------------------------------------
# Latency anomaly tests
# ---------------------------------------------------------


def test_latency_below_threshold_returns_none():
    result = detect_latency_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_latency_ms=120,
        expected_latency_ms=100,
    )

    assert result is None


def test_latency_low_anomaly():
    result = detect_latency_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_latency_ms=160,
        expected_latency_ms=100,
    )

    assert result is not None
    assert result.anomaly_type == "LATENCY"
    assert result.severity == "LOW"


def test_latency_medium_anomaly():
    result = detect_latency_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_latency_ms=250,
        expected_latency_ms=100,
    )

    assert result is not None
    assert result.anomaly_type == "LATENCY"
    assert result.severity == "MEDIUM"


def test_latency_high_anomaly():
    result = detect_latency_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_latency_ms=350,
        expected_latency_ms=100,
    )

    assert result is not None
    assert result.anomaly_type == "LATENCY"
    assert result.severity == "HIGH"


def test_latency_invalid_expected_value():
    with pytest.raises(ValueError):
        detect_latency_anomaly(
            service_name="payment-service",
            timestamp=TIMESTAMP,
            observed_latency_ms=100,
            expected_latency_ms=0,
        )


def test_latency_negative_observed_value():
    with pytest.raises(ValueError):
        detect_latency_anomaly(
            service_name="payment-service",
            timestamp=TIMESTAMP,
            observed_latency_ms=-10,
            expected_latency_ms=100,
        )


# ---------------------------------------------------------
# Error-rate anomaly tests
# ---------------------------------------------------------


def test_error_rate_below_threshold_returns_none():
    result = detect_error_rate_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_error_rate=4,
        expected_error_rate=2,
    )

    assert result is None


def test_error_rate_low_anomaly():
    result = detect_error_rate_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_error_rate=8,
        expected_error_rate=2,
    )

    assert result is not None
    assert result.anomaly_type == "ERROR_RATE"
    assert result.severity == "LOW"


def test_error_rate_medium_anomaly():
    result = detect_error_rate_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_error_rate=15,
        expected_error_rate=2,
    )

    assert result is not None
    assert result.anomaly_type == "ERROR_RATE"
    assert result.severity == "MEDIUM"


def test_error_rate_high_anomaly():
    result = detect_error_rate_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_error_rate=25,
        expected_error_rate=2,
    )

    assert result is not None
    assert result.anomaly_type == "ERROR_RATE"
    assert result.severity == "HIGH"


def test_error_rate_invalid_observed_value():
    with pytest.raises(ValueError):
        detect_error_rate_anomaly(
            service_name="payment-service",
            timestamp=TIMESTAMP,
            observed_error_rate=101,
            expected_error_rate=2,
        )


# ---------------------------------------------------------
# Metric anomaly tests
# ---------------------------------------------------------


def test_metric_below_threshold_returns_none():
    result = detect_metric_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_value=45,
        expected_value=40,
        metric_name="cpu.utilization",
    )

    assert result is None


def test_metric_low_anomaly():
    result = detect_metric_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_value=60,
        expected_value=40,
        metric_name="cpu.utilization",
    )

    assert result is not None
    assert result.anomaly_type == "METRIC"
    assert result.severity == "LOW"


def test_metric_medium_anomaly():
    result = detect_metric_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_value=100,
        expected_value=40,
        metric_name="cpu.utilization",
    )

    assert result is not None
    assert result.anomaly_type == "METRIC"
    assert result.severity == "MEDIUM"


def test_metric_high_anomaly():
    result = detect_metric_anomaly(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_value=140,
        expected_value=40,
        metric_name="cpu.utilization",
    )

    assert result is not None
    assert result.anomaly_type == "METRIC"
    assert result.severity == "HIGH"


def test_metric_invalid_expected_value():
    with pytest.raises(ValueError):
        detect_metric_anomaly(
            service_name="payment-service",
            timestamp=TIMESTAMP,
            observed_value=100,
            expected_value=0,
            metric_name="cpu.utilization",
        )


# ---------------------------------------------------------
# Unified service tests
# ---------------------------------------------------------


def test_unified_latency_detection():
    result = anomaly_detection_service.detect_latency(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_latency_ms=250,
        expected_latency_ms=100,
    )

    assert result is not None
    assert result.anomaly_type == "LATENCY"


def test_unified_error_rate_detection():
    result = anomaly_detection_service.detect_error_rate(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_error_rate=15,
        expected_error_rate=2,
    )

    assert result is not None
    assert result.anomaly_type == "ERROR_RATE"


def test_unified_metric_detection():
    result = anomaly_detection_service.detect_metric(
        service_name="payment-service",
        timestamp=TIMESTAMP,
        observed_value=100,
        expected_value=40,
        metric_name="cpu.utilization",
    )

    assert result is not None
    assert result.anomaly_type == "METRIC"