"""API tests for session lifecycle endpoints."""

from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifierd.main import app
from amplifierd.routers.mount_plans import get_mount_plan_service
from amplifierd.routers.sessions import get_session_state_service


@pytest.fixture
def mock_session_metadata() -> SessionMetadata:
    """Sample session metadata for testing.

    Returns:
        Sample session metadata
    """
    return SessionMetadata(
        session_id="test_session_123",
        status=SessionStatus.CREATED,
        profile_name="foundation/base",
        mount_plan_path="state/sessions/test_session_123/mount_plan.json",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_mount_plan() -> dict:
    """Sample mount plan for testing.

    Returns:
        Sample mount plan dict with basic structure
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
                "module_id": "foundation/base.agents.test-agent",
                "module_type": "agent",
                "content": "# Test Agent",
            }
        ],
    }


@pytest.fixture
def mock_mount_plan_service(mock_mount_plan: dict) -> Mock:
    """Mock mount plan service.

    Args:
        mock_mount_plan: Sample mount plan fixture

    Returns:
        Mock service
    """
    service = Mock()
    service.generate_mount_plan = Mock(return_value=mock_mount_plan)
    return service


@pytest.fixture
def mock_session_state_service(mock_session_metadata: SessionMetadata) -> Mock:
    """Mock session state service.

    Args:
        mock_session_metadata: Sample session metadata fixture

    Returns:
        Mock service
    """
    service = Mock()
    service.create_session = Mock(return_value=mock_session_metadata)
    service.start_session = Mock()
    service.complete_session = Mock()
    service.fail_session = Mock()
    service.terminate_session = Mock()
    service.get_session = Mock(return_value=mock_session_metadata)
    service.list_sessions = Mock(return_value=[mock_session_metadata])
    service.get_active_sessions = Mock(return_value=[mock_session_metadata])
    service.append_message = Mock()
    service.get_transcript = Mock(return_value=[])
    service.delete_session = Mock(return_value=True)
    service.cleanup_old_sessions = Mock(return_value=5)
    return service


@pytest.fixture
def mock_amplified_directory_service(monkeypatch):
    """Mock AmplifiedDirectoryService to bypass directory validation.

    Args:
        monkeypatch: Pytest monkeypatch fixture

    Yields:
        None
    """
    from amplifierd.models.amplified_directories import AmplifiedDirectory

    mock_directory = AmplifiedDirectory(
        relative_path=".",
        default_profile="foundation/base",
        metadata={"default_profile": "foundation/base"},
        created_at=datetime.now(UTC),
        path="/data",
        is_amplified=True,
    )

    mock_service = Mock()
    mock_service.get = Mock(return_value=mock_directory)

    # Monkeypatch the AmplifiedDirectoryService class
    monkeypatch.setattr(
        "amplifierd.routers.sessions.AmplifiedDirectoryService",
        lambda data_dir: mock_service
    )
    yield


@pytest.fixture
def override_services(
    mock_mount_plan_service: Mock,
    mock_session_state_service: Mock,
    mock_amplified_directory_service,
):
    """Override service dependencies with test services.

    Args:
        mock_mount_plan_service: Mock mount plan service
        mock_session_state_service: Mock session state service
        mock_amplified_directory_service: Mock amplified directory service

    Yields:
        None
    """
    app.dependency_overrides[get_mount_plan_service] = lambda: mock_mount_plan_service
    app.dependency_overrides[get_session_state_service] = lambda: mock_session_state_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_services) -> TestClient:
    """FastAPI test client with mocked dependencies.

    Args:
        override_services: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.mark.integration
class TestSessionsAPI:
    """Test session API endpoints."""

    # --- Lifecycle Tests ---

    def test_create_session_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/ creates session successfully."""
        # Make request
        response = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"})

        # Assert response
        assert response.status_code == 201
        data = response.json()
        assert data["sessionId"] == "test_session_123"
        assert data["status"] == "created"
        assert data["profileName"] == "foundation/base"

        # Verify service was called
        mock_session_state_service.create_session.assert_called_once()

    def test_create_session_with_settings_overrides(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/sessions/ accepts settings overrides."""
        # Make request with settings overrides
        response = client.post(
            "/api/v1/sessions/",
            json={
                "profile_name": "foundation/base",
                "settings_overrides": {"llm": {"model": "gpt-4"}},
            },
        )

        # Assert response
        assert response.status_code == 201

        # Verify mount plan service was called with profile_name and amplified_dir
        from pathlib import Path

        mock_mount_plan_service.generate_mount_plan.assert_called_once_with("foundation/base", Path("/data"))

    def test_create_session_invalid_profile(self, client: TestClient, mock_mount_plan_service: Mock) -> None:
        """Test POST /api/v1/sessions/ returns 404 for invalid profile."""
        # Setup mock to raise FileNotFoundError
        mock_mount_plan_service.generate_mount_plan.side_effect = FileNotFoundError("Profile not found")

        # Make request
        response = client.post("/api/v1/sessions/", json={"profile_name": "nonexistent"})

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_start_session_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/start transitions to ACTIVE."""
        # Make request
        response = client.post("/api/v1/sessions/test_session_123/start")

        # Assert
        assert response.status_code == 204

        # Verify service was called
        mock_session_state_service.start_session.assert_called_once_with("test_session_123")

    def test_start_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/start returns 404 for missing session."""
        # Setup mock to raise FileNotFoundError
        mock_session_state_service.start_session.side_effect = FileNotFoundError("Session not found")

        # Make request
        response = client.post("/api/v1/sessions/nonexistent/start")

        # Assert
        assert response.status_code == 404

    def test_complete_session_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/complete transitions to COMPLETED."""
        # Make request
        response = client.post("/api/v1/sessions/test_session_123/complete")

        # Assert
        assert response.status_code == 204

        # Verify service was called
        mock_session_state_service.complete_session.assert_called_once_with("test_session_123")

    def test_fail_session_with_error(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/fail transitions to FAILED with error."""
        # Make request
        response = client.post(
            "/api/v1/sessions/test_session_123/fail",
            json={
                "error_message": "LLM API timeout",
                "error_details": {"api": "openai", "timeout_seconds": 30},
            },
        )

        # Assert
        assert response.status_code == 204

        # Verify service was called with error details
        mock_session_state_service.fail_session.assert_called_once_with(
            session_id="test_session_123",
            error_message="LLM API timeout",
            error_details={"api": "openai", "timeout_seconds": 30},
        )

    def test_terminate_session_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/terminate transitions to TERMINATED."""
        # Make request
        response = client.post("/api/v1/sessions/test_session_123/terminate")

        # Assert
        assert response.status_code == 204

        # Verify service was called
        mock_session_state_service.terminate_session.assert_called_once_with("test_session_123")

    # --- Query Tests ---

    def test_get_session_success(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions/{session_id} returns session metadata."""
        # Make request
        response = client.get("/api/v1/sessions/test_session_123")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["sessionId"] == "test_session_123"
        assert data["status"] == "created"
        assert data["profileName"] == "foundation/base"

    def test_get_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/{session_id} returns 404 for missing session."""
        # Setup mock to return None
        mock_session_state_service.get_session.return_value = None

        # Make request
        response = client.get("/api/v1/sessions/nonexistent")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_sessions_no_filters(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions/ returns all sessions."""
        # Make request
        response = client.get("/api/v1/sessions/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sessionId"] == "test_session_123"

    def test_list_sessions_with_filters(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/ applies filters correctly."""
        # Make request with filters
        response = client.get(
            "/api/v1/sessions/",
            params={
                "status": "active",
                "profile_name": "foundation/base",
                "limit": 10,
            },
        )

        # Assert
        assert response.status_code == 200

        # Verify service was called with filters
        mock_session_state_service.list_sessions.assert_called_once_with(
            status=SessionStatus.ACTIVE,
            profile_name="foundation/base",
            amplified_dir=None,
            limit=10,
        )

    def test_get_active_sessions(self, client: TestClient) -> None:
        """Test GET /api/v1/sessions/active/list returns only active sessions."""
        # Make request
        response = client.get("/api/v1/sessions/active/list")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    # --- Transcript Tests ---

    def test_append_message_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/messages appends message."""
        # Make request
        response = client.post(
            "/api/v1/sessions/test_session_123/messages",
            json={
                "role": "user",
                "content": "Hello, world!",
                "agent": "user",
                "token_count": 5,
            },
        )

        # Assert
        assert response.status_code == 201

        # Verify service was called
        mock_session_state_service.append_message.assert_called_once_with(
            session_id="test_session_123",
            role="user",
            content="Hello, world!",
            agent="user",
            token_count=5,
        )

    def test_append_message_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/messages returns 404 for missing session."""
        # Setup mock to return None for get_session
        mock_session_state_service.get_session.return_value = None

        # Make request
        response = client.post(
            "/api/v1/sessions/nonexistent/messages",
            json={"role": "user", "content": "Hello"},
        )

        # Assert
        assert response.status_code == 404

    def test_get_transcript_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/{session_id}/transcript returns messages."""
        # Setup mock to return messages
        from amplifier_library.models.sessions import SessionMessage

        mock_session_state_service.get_transcript.return_value = [
            SessionMessage(
                role="user",
                content="Hello",
                timestamp=datetime.now(UTC),
                agent=None,
                token_count=None,
            )
        ]

        # Make request
        response = client.get("/api/v1/sessions/test_session_123/transcript")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_get_transcript_with_limit(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/{session_id}/transcript respects limit parameter."""
        # Make request with limit
        response = client.get("/api/v1/sessions/test_session_123/transcript?limit=10")

        # Assert
        assert response.status_code == 200

        # Verify service was called with limit
        mock_session_state_service.get_transcript.assert_called_once_with("test_session_123", limit=10)

    def test_get_transcript_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/{session_id}/transcript returns 404 for missing session."""
        # Setup mock to return None for get_session
        mock_session_state_service.get_session.return_value = None

        # Make request
        response = client.get("/api/v1/sessions/nonexistent/transcript")

        # Assert
        assert response.status_code == 404

    # --- Management Tests ---

    def test_delete_session_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test DELETE /api/v1/sessions/{session_id} deletes session."""
        # Make request
        response = client.delete("/api/v1/sessions/test_session_123")

        # Assert
        assert response.status_code == 204

        # Verify service was called
        mock_session_state_service.delete_session.assert_called_once_with("test_session_123")

    def test_delete_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test DELETE /api/v1/sessions/{session_id} returns 404 for missing session."""
        # Setup mock to return False
        mock_session_state_service.delete_session.return_value = False

        # Make request
        response = client.delete("/api/v1/sessions/nonexistent")

        # Assert
        assert response.status_code == 404

    def test_cleanup_old_sessions_success(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/cleanup removes old sessions."""
        # Make request
        response = client.post("/api/v1/sessions/cleanup", json={"older_than_days": 60})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "removed_count" in data
        assert data["removed_count"] == 5

        # Verify service was called
        mock_session_state_service.cleanup_old_sessions.assert_called_once_with(older_than_days=60)

    def test_cleanup_old_sessions_default_threshold(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/cleanup uses default threshold."""
        # Make request without threshold
        response = client.post("/api/v1/sessions/cleanup", json={})

        # Assert
        assert response.status_code == 200

        # Verify service was called with default (30 days)
        mock_session_state_service.cleanup_old_sessions.assert_called_once_with(older_than_days=30)

    def test_get_mount_plan_success(
        self, client: TestClient, mock_session_state_service: Mock, mock_mount_plan: dict, tmp_path
    ) -> None:
        """Test GET /api/v1/sessions/{session_id}/mount-plan returns mount plan."""
        # Create mock mount plan file
        import json

        session_dir = tmp_path / "sessions" / "test_session_123"
        session_dir.mkdir(parents=True)
        mount_plan_path = session_dir / "mount_plan.json"
        mount_plan_path.write_text(json.dumps(mock_mount_plan))

        # Mock get_state_dir to return tmp_path
        import amplifierd.routers.sessions

        original_get_state_dir = amplifierd.routers.sessions.get_state_dir
        amplifierd.routers.sessions.get_state_dir = lambda: tmp_path

        try:
            # Make request
            response = client.get("/api/v1/sessions/test_session_123/mount-plan")

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["session"]["sessionId"] == "test_session_123"
            assert "mountPoints" in data
        finally:
            # Restore original function
            amplifierd.routers.sessions.get_state_dir = original_get_state_dir

    def test_get_mount_plan_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test GET /api/v1/sessions/{session_id}/mount-plan returns 404 for missing session."""
        # Setup mock to return None for get_session
        mock_session_state_service.get_session.return_value = None

        # Make request
        response = client.get("/api/v1/sessions/nonexistent/mount-plan")

        # Assert
        assert response.status_code == 404

    # --- Error Handling Tests ---

    def test_create_session_unexpected_error(
        self, client: TestClient, mock_mount_plan_service: Mock, mock_session_state_service: Mock
    ) -> None:
        """Test create_session with unexpected error during mount plan generation."""
        # Mock mount plan service to raise generic Exception
        mock_mount_plan_service.generate_mount_plan = Mock(
            side_effect=Exception("Unexpected error in mount plan generation")
        )

        response = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"})

        assert response.status_code == 500
        assert "Failed to create session" in response.json()["detail"]

    def test_start_session_unexpected_error(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test start_session with unexpected error in state service."""
        # Mock service.start_session to raise generic Exception
        mock_session_state_service.start_session.side_effect = Exception("Unexpected state error")

        response = client.post("/api/v1/sessions/test_session_123/start")

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

    def test_complete_session_unexpected_error(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test complete_session with unexpected error."""
        mock_session_state_service.complete_session.side_effect = Exception("Unexpected error")

        response = client.post("/api/v1/sessions/test_session_123/complete")

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

    def test_fail_terminate_unexpected_errors(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test fail and terminate endpoints with unexpected errors."""
        # Test fail
        mock_session_state_service.fail_session.side_effect = Exception("Fail error")
        response = client.post("/api/v1/sessions/test_session_123/fail", json={"error_message": "test"})
        assert response.status_code == 500

        # Reset and test terminate
        mock_session_state_service.fail_session.side_effect = None
        mock_session_state_service.terminate_session.side_effect = Exception("Terminate error")
        response = client.post("/api/v1/sessions/test_session_123/terminate")
        assert response.status_code == 500
