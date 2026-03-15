"""API tests for the health endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a plain TestClient — health needs no mocks."""
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    """Health endpoint should always return 200 OK."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_correct_schema(client: TestClient) -> None:
    """Health response should contain status, app and version."""
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "FeedPilot API"
    assert "version" in data


def test_root_returns_running_message(client: TestClient) -> None:
    """Root endpoint should confirm API is running."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "FeedPilot API is running"