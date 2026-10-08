from datetime import datetime

from backend.app.telemetry.anomaly import Anomaly
from backend.app.telemetry.anomaly_detector import (
    detect_error_rate_anomaly,
    detect_latency_anomaly,
    detect_metric_anomaly,
)


class AnomalyDetectionService:
    """
    Unified service for detecting anomalies across
    latency, error rate, and metrics.
    """

    def detect_latency(
        self,
        service_name: str,
        timestamp: datetime,
        observed_latency_ms: float,
        expected_latency_ms: float,
    ) -> Anomaly | None:
        """Detect a latency anomaly."""

        return detect_latency_anomaly(
            service_name=service_name,
            timestamp=timestamp,
            observed_latency_ms=observed_latency_ms,
            expected_latency_ms=expected_latency_ms,
        )

    def detect_error_rate(
        self,
        service_name: str,
        timestamp: datetime,
        observed_error_rate: float,
        expected_error_rate: float,
    ) -> Anomaly | None:
        """Detect an error-rate anomaly."""

        return detect_error_rate_anomaly(
            service_name=service_name,
            timestamp=timestamp,
            observed_error_rate=observed_error_rate,
            expected_error_rate=expected_error_rate,
        )

    def detect_metric(
        self,
        service_name: str,
        timestamp: datetime,
        observed_value: float,
        expected_value: float,
        metric_name: str,
    ) -> Anomaly | None:
        """Detect a metric anomaly."""

        return detect_metric_anomaly(
            service_name=service_name,
            timestamp=timestamp,
            observed_value=observed_value,
            expected_value=expected_value,
            metric_name=metric_name,
        )


anomaly_detection_service = AnomalyDetectionService()