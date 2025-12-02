"""API tests for mount plan endpoints."""

from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.mount_plans import get_mount_plan_service


@pytest.fixture
def mock_mount_plan() -> dict:
    """Sample mount plan for testing.

    Returns:
        Sample mount plan dict with realistic data
    """
    return {
        "format_version": "1.0",
        "session": {
            "session_id": "test_session_123",
            "profile_id": "foundation/base",
            "created_at": datetime.now(UTC).isoformat(),
            "settings": {},
        },
        "mount_points": [
            {
                "mount_type": "embedded",
                "module_id": "foundation/base.agents.zen-architect",
                "module_type": "agent",
                "content": "# Zen Architect\n\nYou are a zen architect.",
            },
            {
                "mount_type": "embedded",
                "module_id": "foundation/base.context.philosophy",
                "module_type": "context",
                "content": "# Philosophy\n\nBe simple and elegant.",
            },
        ],
    }


@pytest.fixture
def mock_mount_plan_service() -> Mock:
    """Mock mount plan service.

    Returns:
        Mock service for testing
    """
    service = Mock()
    service.generate_mount_plan = Mock()
    return service


@pytest.fixture
def override_mount_plan_service(mock_mount_plan_service: Mock):
    """Override mount plan service dependency with test service.

    Args:
        mock_mount_plan_service: Mock service

    Yields:
        None
    """
    app.dependency_overrides[get_mount_plan_service] = lambda: mock_mount_plan_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_mount_plan_service) -> TestClient:
    """FastAPI test client with mocked dependencies.

    Args:
        override_mount_plan_service: Dependency override fixture

    Returns:
        Test client for making API requests
    """
    return TestClient(app)


@pytest.mark.integration
class TestMountPlansAPI:
    """Test mount plan API endpoints."""

    def test_generate_mount_plan_success(
        self, client: TestClient, mock_mount_plan: dict, mock_mount_plan_service: Mock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate returns 201 with valid response."""
        # Setup mock
        mock_mount_plan_service.generate_mount_plan.return_value = mock_mount_plan

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "foundation/base", "amplified_dir": "/tmp/test"}
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()

        # Verify structure
        assert "formatVersion" in data
        assert "session" in data
        assert "mountPoints" in data

        # Verify session data
        assert data["session"]["sessionId"] == "test_session_123"
        assert data["session"]["profileId"] == "foundation/base"

        # Verify mount points
        assert len(data["mountPoints"]) == 2
        assert data["mountPoints"][0]["moduleType"] == "agent"
        assert data["mountPoints"][1]["moduleType"] == "context"

        # Verify service was called correctly
        mock_mount_plan_service.generate_mount_plan.assert_called_once()

    def test_generate_mount_plan_missing_profile(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/mount-plans/generate returns 404 for missing profile."""
        # Setup mock to raise FileNotFoundError
        mock_mount_plan_service.generate_mount_plan.side_effect = FileNotFoundError("Profile not found: nonexistent")

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "nonexistent", "amplified_dir": "/tmp/test"}
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_generate_mount_plan_invalid_profile_id(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/mount-plans/generate returns 400 for invalid profile ID."""
        # Setup mock to raise ValueError
        mock_mount_plan_service.generate_mount_plan.side_effect = ValueError("Invalid profile ID format")

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "invalid//format", "amplified_dir": "/tmp/test"}
        )

        # Assert
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_generate_mount_plan_with_settings_overrides(
        self, client: TestClient, mock_mount_plan: dict, mock_mount_plan_service: Mock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate accepts settings overrides."""
        # Setup mock
        mock_mount_plan_service.generate_mount_plan.return_value = mock_mount_plan

        # Make request with settings overrides
        response = client.post(
            "/api/v1/mount-plans/generate",
            json={
                "profile_id": "foundation/base",
                "amplified_dir": "/tmp/test",
                "settings_overrides": {"llm": {"model": "gpt-4", "temperature": 0.7}},
            },
        )

        # Assert response
        assert response.status_code == 201

        # Verify service was called with profile_id and amplified_dir
        from pathlib import Path

        mock_mount_plan_service.generate_mount_plan.assert_called_once_with("foundation/base", Path("/tmp/test"))

    def test_generate_mount_plan_with_custom_session_id(
        self, client: TestClient, mock_mount_plan_service: Mock
    ) -> None:
        """Test POST /api/v1/mount-plans/generate accepts custom session ID."""
        # Create mount plan with custom session ID
        custom_mount_plan = {
            "format_version": "1.0",
            "session": {
                "session_id": "my-custom-session-123",
                "profile_id": "foundation/base",
                "created_at": datetime.now(UTC).isoformat(),
                "settings": {},
            },
            "mount_points": [],
        }

        # Setup mock
        mock_mount_plan_service.generate_mount_plan.return_value = custom_mount_plan

        # Make request with custom session ID
        response = client.post(
            "/api/v1/mount-plans/generate",
            json={
                "profile_id": "foundation/base",
                "amplified_dir": "/tmp/test",
                "session_id": "my-custom-session-123",
            },
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert data["session"]["sessionId"] == "my-custom-session-123"

        # Verify service was called with profile_id and amplified_dir
        from pathlib import Path

        mock_mount_plan_service.generate_mount_plan.assert_called_once_with("foundation/base", Path("/tmp/test"))

    def test_generate_mount_plan_internal_error(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/mount-plans/generate returns 500 for unexpected errors."""
        # Setup mock to raise unexpected error
        mock_mount_plan_service.generate_mount_plan.side_effect = RuntimeError("Unexpected error")

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "foundation/base", "amplified_dir": "/tmp/test"}
        )

        # Assert
        assert response.status_code == 500
        assert "failed to generate mount plan" in response.json()["detail"].lower()

    def test_generate_mount_plan_missing_profile_id(self, client: TestClient) -> None:
        """Test POST /api/v1/mount-plans/generate returns 422 for missing profile_id."""
        # Make request without profile_id
        response = client.post("/api/v1/mount-plans/generate", json={})

        # Assert validation error
        assert response.status_code == 422
        errors = response.json()["detail"]
        # FastAPI converts field names to camelCase in validation errors
        assert any(error["loc"] == ["body", "profileId"] for error in errors)

    def test_generate_mount_plan_empty_mount_points(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/mount-plans/generate handles empty mount points."""
        # Create mount plan with no mount points
        empty_mount_plan = {
            "format_version": "1.0",
            "session": {
                "session_id": "test_session_456",
                "profile_id": "foundation/minimal",
                "created_at": datetime.now(UTC).isoformat(),
                "settings": {},
            },
            "mount_points": [],
        }

        # Setup mock
        mock_mount_plan_service.generate_mount_plan.return_value = empty_mount_plan

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "foundation/minimal", "amplified_dir": "/tmp/test"}
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert data["mountPoints"] == []
        assert data["session"]["sessionId"] == "test_session_456"

    def test_generate_mount_plan_multiple_module_types(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/mount-plans/generate handles multiple agents and contexts."""
        # Create mount plan with multiple agents and contexts
        diverse_mount_plan = {
            "format_version": "1.0",
            "session": {
                "session_id": "test_session_789",
                "profile_id": "foundation/full",
                "created_at": datetime.now(UTC).isoformat(),
                "settings": {},
            },
            "mount_points": [
                {
                    "mount_type": "embedded",
                    "module_id": "foundation/full.agents.test-agent",
                    "module_type": "agent",
                    "content": "# Test Agent",
                },
                {
                    "mount_type": "embedded",
                    "module_id": "foundation/full.agents.another-agent",
                    "module_type": "agent",
                    "content": "# Another Agent",
                },
                {
                    "mount_type": "embedded",
                    "module_id": "foundation/full.context.test-context",
                    "module_type": "context",
                    "content": "# Test Context",
                },
                {
                    "mount_type": "embedded",
                    "module_id": "foundation/full.context.another-context",
                    "module_type": "context",
                    "content": "# Another Context",
                },
            ],
        }

        # Setup mock
        mock_mount_plan_service.generate_mount_plan.return_value = diverse_mount_plan

        # Make request
        response = client.post(
            "/api/v1/mount-plans/generate", json={"profile_id": "foundation/full", "amplified_dir": "/tmp/test"}
        )

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert len(data["mountPoints"]) == 4

        # Verify all module types present
        module_types = {mp["moduleType"] for mp in data["mountPoints"]}
        assert module_types == {"agent", "context"}
