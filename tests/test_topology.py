from datetime import datetime, timezone

import pytest

from backend.app.telemetry.topology import (
    DependencyEdge,
    ServiceNode,
)


def test_service_node_creation():
    timestamp = datetime.now(timezone.utc)

    service = ServiceNode(
        service_name="payment-service",
        first_seen=timestamp,
        last_seen=timestamp,
    )

    assert service.service_name == "payment-service"
    assert service.first_seen == timestamp
    assert service.last_seen == timestamp


def test_service_node_rejects_empty_name():
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        ServiceNode(
            service_name="",
            first_seen=timestamp,
            last_seen=timestamp,
        )


def test_service_node_rejects_whitespace_name():
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        ServiceNode(
            service_name="   ",
            first_seen=timestamp,
            last_seen=timestamp,
        )


def test_dependency_edge_creation():
    timestamp = datetime.now(timezone.utc)

    edge = DependencyEdge(
        source_service="api-gateway",
        target_service="payment-service",
        first_seen=timestamp,
        last_seen=timestamp,
    )

    assert edge.source_service == "api-gateway"
    assert edge.target_service == "payment-service"
    assert edge.first_seen == timestamp
    assert edge.last_seen == timestamp


def test_dependency_edge_rejects_self_dependency():
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        DependencyEdge(
            source_service="payment-service",
            target_service="payment-service",
            first_seen=timestamp,
            last_seen=timestamp,
        )


def test_dependency_edge_rejects_empty_source():
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        DependencyEdge(
            source_service="",
            target_service="payment-service",
            first_seen=timestamp,
            last_seen=timestamp,
        )


def test_dependency_edge_rejects_empty_target():
    timestamp = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        DependencyEdge(
            source_service="api-gateway",
            target_service="",
            first_seen=timestamp,
            last_seen=timestamp,
        )