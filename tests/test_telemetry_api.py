from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_trace_api_returns_500_on_database_error(client):
    with patch(
        "backend.app.api.routes.telemetry.ingest_trace",
        new=AsyncMock(side_effect=SQLAlchemyError("database failure")),
    ):
        response = client.post(
            "/telemetry/traces",
            json={
                "trace_id": "m584-error-trace",
                "span_id": "m584-error-span",
                "service_name": "test-service",
                "operation_name": "test-operation",
                "timestamp": "2026-09-21T10:00:00Z",
                "duration_ms": 25.5,
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to persist telemetry event"
    }

def test_trace_api_rejects_empty_trace_id(client):
    response = client.post(
        "/telemetry/traces",
        json={
            "trace_id": "",
            "span_id": "test-span",
            "service_name": "test-service",
            "operation_name": "test-operation",
            "timestamp": "2026-09-21T10:00:00Z",
            "duration_ms": 25.5,
        },
    )

    assert response.status_code == 422


def test_trace_api_rejects_negative_duration(client):
    response = client.post(
        "/telemetry/traces",
        json={
            "trace_id": "test-trace",
            "span_id": "test-span",
            "service_name": "test-service",
            "operation_name": "test-operation",
            "timestamp": "2026-09-21T10:00:00Z",
            "duration_ms": -10,
        },
    )

    assert response.status_code == 422


def test_trace_api_rejects_invalid_status(client):
    response = client.post(
        "/telemetry/traces",
        json={
            "trace_id": "test-trace",
            "span_id": "test-span",
            "service_name": "test-service",
            "operation_name": "test-operation",
            "timestamp": "2026-09-21T10:00:00Z",
            "duration_ms": 25.5,
            "status": "INVALID",
        },
    )

    assert response.status_code == 422

def test_log_api_rejects_empty_service_name(client):
    response = client.post(
        "/telemetry/logs",
        json={
            "timestamp": "2026-09-21T10:00:00Z",
            "service_name": "",
            "message": "Test log message",
        },
    )

    assert response.status_code == 422


def test_log_api_rejects_whitespace_message(client):
    response = client.post(
        "/telemetry/logs",
        json={
            "timestamp": "2026-09-21T10:00:00Z",
            "service_name": "test-service",
            "message": "   ",
        },
    )

    assert response.status_code == 422


def test_log_api_rejects_invalid_timestamp(client):
    response = client.post(
        "/telemetry/logs",
        json={
            "timestamp": "not-a-timestamp",
            "service_name": "test-service",
            "message": "Test log message",
        },
    )

    assert response.status_code == 422

def test_metric_api_rejects_empty_service_name(client):
    response = client.post(
        "/telemetry/metrics",
        json={
            "timestamp": "2026-09-21T10:00:00Z",
            "service_name": "",
            "metric_name": "cpu",
            "metric_value": 75.5,
        },
    )

    assert response.status_code == 422


def test_metric_api_rejects_whitespace_metric_name(client):
    response = client.post(
        "/telemetry/metrics",
        json={
            "timestamp": "2026-09-21T10:00:00Z",
            "service_name": "test-service",
            "metric_name": "   ",
            "metric_value": 75.5,
        },
    )

    assert response.status_code == 422


def test_metric_api_rejects_invalid_metric_value(client):
    response = client.post(
        "/telemetry/metrics",
        json={
            "timestamp": "2026-09-21T10:00:00Z",
            "service_name": "test-service",
            "metric_name": "cpu",
            "metric_value": "not-a-number",
        },
    )

    assert response.status_code == 422

def test_log_api_returns_500_on_database_error(client):
    with patch(
        "backend.app.api.routes.telemetry.ingest_log",
        new=AsyncMock(side_effect=SQLAlchemyError("database failure")),
    ):
        response = client.post(
            "/telemetry/logs",
            json={
                "timestamp": "2026-09-21T10:00:00Z",
                "service_name": "test-service",
                "message": "Test log message",
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to persist telemetry event"
    }


def test_metric_api_returns_500_on_database_error(client):
    with patch(
        "backend.app.api.routes.telemetry.ingest_metric",
        new=AsyncMock(side_effect=SQLAlchemyError("database failure")),
    ):
        response = client.post(
            "/telemetry/metrics",
            json={
                "timestamp": "2026-09-21T10:00:00Z",
                "service_name": "test-service",
                "metric_name": "cpu_usage",
                "metric_value": 75.5,
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to persist telemetry event"
    }