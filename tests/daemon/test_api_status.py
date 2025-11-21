"""
Integration tests for status API endpoints.

Tests health check and status endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.mark.integration
class TestStatusAPI:
    """Test status API endpoints."""

    def test_root_endpoint_returns_api_info(self, client: TestClient) -> None:
        """Test GET / returns API information."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "amplifierd"
        assert "version" in data
        assert "docs" in data

    def test_status_endpoint_returns_running(self, client: TestClient) -> None:
        """Test GET /api/v1/status returns status information."""
        response = client.get("/api/v1/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "version" in data
        assert "uptimeSeconds" in data

    def test_status_uptime_is_positive(self, client: TestClient) -> None:
        """Test status endpoint returns positive uptime."""
        response = client.get("/api/v1/status")

        data = response.json()
        assert data["uptimeSeconds"] >= 0

    def test_health_check_returns_healthy(self, client: TestClient) -> None:
        """Test GET /api/v1/health returns healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_status_endpoints_always_available(self, client: TestClient) -> None:
        """Test status endpoints work even when no sessions exist."""
        # Status should work without any sessions
        response = client.get("/api/v1/status")
        assert response.status_code == 200

        response = client.get("/api/v1/health")
        assert response.status_code == 200
