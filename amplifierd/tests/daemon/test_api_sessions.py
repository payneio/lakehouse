"""API tests for session lifecycle endpoints."""

from datetime import UTC
from datetime import datetime
from typing import Any
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
        status=SessionStatus.ACTIVE,
        profile_name="foundation/base",
        mount_plan_path="state/sessions/test_session_123/mount_plan.json",
        created_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
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
        assert data["status"] == "active"
        assert data["profileName"] == "foundation/base"
        assert data["startedAt"] is not None

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

        # Verify mount plan service was called with profile_name
        # The amplified_dir comes from the mock_amplified_directory_service fixture
        mock_mount_plan_service.generate_mount_plan.assert_called_once()
        call_args = mock_mount_plan_service.generate_mount_plan.call_args
        assert call_args[0][0] == "foundation/base"  # profile_name
        # amplified_dir is the second argument, comes from config

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

    def test_start_session_already_active_is_noop(
        self, client: TestClient, mock_session_state_service: Mock
    ) -> None:
        """Test POST /api/v1/sessions/{id}/start is no-op for ACTIVE sessions."""
        # Should succeed without error
        response = client.post("/api/v1/sessions/test_session_123/start")
        assert response.status_code == 204
        # Verify service method was called
        mock_session_state_service.start_session.assert_called_once_with("test_session_123")

    def test_start_session_rejects_terminal_state(
        self, client: TestClient, mock_session_state_service: Mock
    ) -> None:
        """Test POST /api/v1/sessions/{id}/start returns 400 for terminal state."""
        mock_session_state_service.start_session.side_effect = ValueError(
            "Cannot start session in terminal state"
        )
        response = client.post("/api/v1/sessions/test_session_123/start")
        assert response.status_code == 400
        assert "terminal state" in response.json()["detail"].lower()

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
        assert data["status"] == "active"
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

    # --- Clone Session Tests ---

    def test_clone_session_success(
        self, client: TestClient, mock_session_state_service: Mock, mock_mount_plan: dict, tmp_path
    ) -> None:
        """Test POST /api/v1/sessions/{session_id}/clone creates cloned session."""
        import json

        # Create mock source session directory with mount plan and transcript
        session_dir = tmp_path / "sessions" / "test_session_123"
        session_dir.mkdir(parents=True)
        (session_dir / "mount_plan.json").write_text(json.dumps(mock_mount_plan))
        (session_dir / "transcript.jsonl").write_text('{"role": "user", "content": "Hello"}\n')
        (session_dir / "events.jsonl").write_text('{"event": "test", "ts": "2024-01-01T00:00:00Z"}\n')

        # Mock get_state_dir to return tmp_path
        import amplifierd.routers.sessions

        original_get_state_dir = amplifierd.routers.sessions.get_state_dir
        amplifierd.routers.sessions.get_state_dir = lambda: tmp_path

        # Setup mock to return empty list for subsessions
        mock_session_state_service.list_sessions.return_value = []

        # Track the created session ID and metadata
        created_session_id: str | None = None
        source_metadata = SessionMetadata(
            session_id="test_session_123",
            status=SessionStatus.ACTIVE,
            profile_name="foundation/base",
            mount_plan_path="state/sessions/test_session_123/mount_plan.json",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            amplified_dir=".",
            name="Test Session",
        )

        def mock_get_session(sid: str) -> SessionMetadata | None:
            nonlocal created_session_id
            if sid == "test_session_123":
                return source_metadata
            elif created_session_id and sid == created_session_id:
                return SessionMetadata(
                    session_id=created_session_id,
                    status=SessionStatus.ACTIVE,
                    profile_name="foundation/base",
                    mount_plan_path=f"state/sessions/{created_session_id}/mount_plan.json",
                    created_at=datetime.now(UTC),
                    started_at=datetime.now(UTC),
                    name="Test Session (copy)",
                )
            return None

        def mock_create_session(**kwargs: Any) -> SessionMetadata:
            nonlocal created_session_id
            created_session_id = kwargs.get("session_id")
            return SessionMetadata(
                session_id=created_session_id or "unknown",
                status=SessionStatus.ACTIVE,
                profile_name=kwargs.get("profile_name", "foundation/base"),
                mount_plan_path=f"state/sessions/{created_session_id}/mount_plan.json",
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
            )

        mock_session_state_service.get_session.side_effect = mock_get_session
        mock_session_state_service.create_session.side_effect = mock_create_session

        try:
            # Make request
            response = client.post("/api/v1/sessions/test_session_123/clone")

            # Assert response
            assert response.status_code == 201
            data = response.json()
            assert data["sessionId"].startswith("session_")
            assert data["sessionId"] != "test_session_123"
            assert data["name"] == "Test Session (copy)"

            # Verify create_session was called
            mock_session_state_service.create_session.assert_called_once()
        finally:
            # Restore original function
            amplifierd.routers.sessions.get_state_dir = original_get_state_dir

    def test_clone_session_not_found(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/clone returns 404 for missing session."""
        # Setup mock to return None
        mock_session_state_service.get_session.return_value = None

        # Make request
        response = client.post("/api/v1/sessions/nonexistent/clone")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_clone_session_copies_transcript_and_events(
        self, client: TestClient, mock_session_state_service: Mock, mock_mount_plan: dict, tmp_path
    ) -> None:
        """Test POST /api/v1/sessions/{session_id}/clone copies transcript and events."""
        import json

        # Create source session with transcript and events
        source_dir = tmp_path / "sessions" / "test_session_123"
        source_dir.mkdir(parents=True)
        (source_dir / "mount_plan.json").write_text(json.dumps(mock_mount_plan))
        (source_dir / "transcript.jsonl").write_text(
            '{"role": "user", "content": "Hello"}\n'
            '{"role": "assistant", "content": "Hi there!"}\n'
        )
        (source_dir / "events.jsonl").write_text(
            '{"event": "tool:pre", "ts": "2024-01-01T00:00:00Z"}\n'
            '{"event": "tool:post", "ts": "2024-01-01T00:00:01Z"}\n'
        )
        (source_dir / "profile_context_messages.json").write_text('[{"role": "system", "content": "Context"}]')

        # Mock get_state_dir
        import amplifierd.routers.sessions

        original_get_state_dir = amplifierd.routers.sessions.get_state_dir
        amplifierd.routers.sessions.get_state_dir = lambda: tmp_path

        # Setup mocks
        mock_session_state_service.list_sessions.return_value = []

        source_metadata = SessionMetadata(
            session_id="test_session_123",
            status=SessionStatus.ACTIVE,
            profile_name="foundation/base",
            mount_plan_path="state/sessions/test_session_123/mount_plan.json",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            amplified_dir=".",
            message_count=2,
            agent_invocations=1,
        )

        # Track created session ID
        created_session_id = None

        def mock_create_session(**kwargs):
            nonlocal created_session_id
            created_session_id = kwargs.get("session_id", "session_new123")
            # Create the session directory
            new_dir = tmp_path / "sessions" / created_session_id
            new_dir.mkdir(parents=True, exist_ok=True)
            return SessionMetadata(
                session_id=created_session_id,
                status=SessionStatus.ACTIVE,
                profile_name=kwargs.get("profile_name", "foundation/base"),
                mount_plan_path=f"state/sessions/{created_session_id}/mount_plan.json",
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                amplified_dir=kwargs.get("amplified_dir", "."),
            )

        mock_session_state_service.create_session.side_effect = mock_create_session
        mock_session_state_service.get_session.side_effect = lambda sid: (
            source_metadata if sid == "test_session_123" else
            SessionMetadata(
                session_id=sid,
                status=SessionStatus.ACTIVE,
                profile_name="foundation/base",
                mount_plan_path=f"state/sessions/{sid}/mount_plan.json",
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                amplified_dir=".",
                name="test_session_123 (copy)",
            )
        )

        try:
            # Make request
            response = client.post("/api/v1/sessions/test_session_123/clone")

            # Assert response
            assert response.status_code == 201

            # Verify files were copied to new session directory
            assert created_session_id is not None
            new_dir = tmp_path / "sessions" / created_session_id
            assert (new_dir / "transcript.jsonl").exists()
            assert (new_dir / "events.jsonl").exists()
            assert (new_dir / "profile_context_messages.json").exists()

            # Verify content was copied
            transcript_content = (new_dir / "transcript.jsonl").read_text()
            assert "Hello" in transcript_content
            assert "Hi there!" in transcript_content

            events_content = (new_dir / "events.jsonl").read_text()
            assert "tool:pre" in events_content
            assert "tool:post" in events_content
        finally:
            amplifierd.routers.sessions.get_state_dir = original_get_state_dir

    def test_clone_session_with_subsessions(
        self, client: TestClient, mock_session_state_service: Mock, mock_mount_plan: dict, tmp_path
    ) -> None:
        """Test POST /api/v1/sessions/{session_id}/clone clones subsessions recursively."""
        import json

        # Create source session directories
        parent_dir = tmp_path / "sessions" / "parent_session"
        parent_dir.mkdir(parents=True)
        (parent_dir / "mount_plan.json").write_text(json.dumps(mock_mount_plan))
        (parent_dir / "transcript.jsonl").write_text('{"role": "user", "content": "Parent message"}\n')

        child_dir = tmp_path / "sessions" / "child_session"
        child_dir.mkdir(parents=True)
        (child_dir / "mount_plan.json").write_text(json.dumps(mock_mount_plan))
        (child_dir / "transcript.jsonl").write_text('{"role": "user", "content": "Child message"}\n')

        # Mock get_state_dir
        import amplifierd.routers.sessions

        original_get_state_dir = amplifierd.routers.sessions.get_state_dir
        amplifierd.routers.sessions.get_state_dir = lambda: tmp_path

        # Setup parent and child session metadata
        parent_metadata = SessionMetadata(
            session_id="parent_session",
            status=SessionStatus.ACTIVE,
            profile_name="foundation/base",
            mount_plan_path="state/sessions/parent_session/mount_plan.json",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            amplified_dir=".",
            name="Parent Session",
        )

        child_metadata = SessionMetadata(
            session_id="child_session",
            status=SessionStatus.ACTIVE,
            profile_name="foundation/base",
            mount_plan_path="state/sessions/child_session/mount_plan.json",
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            amplified_dir=".",
            parent_session_id="parent_session",
            name="Child Session",
        )

        # Track created sessions
        created_sessions = []

        def mock_create_session(**kwargs):
            session_id = kwargs.get("session_id", f"session_{len(created_sessions)}")
            created_sessions.append(session_id)
            # Create the session directory
            new_dir = tmp_path / "sessions" / session_id
            new_dir.mkdir(parents=True, exist_ok=True)
            return SessionMetadata(
                session_id=session_id,
                status=SessionStatus.ACTIVE,
                profile_name=kwargs.get("profile_name", "foundation/base"),
                mount_plan_path=f"state/sessions/{session_id}/mount_plan.json",
                created_at=datetime.now(UTC),
                started_at=datetime.now(UTC),
                amplified_dir=kwargs.get("amplified_dir", "."),
                parent_session_id=kwargs.get("parent_session_id"),
            )

        def mock_get_session(sid):
            if sid == "parent_session":
                return parent_metadata
            elif sid == "child_session":
                return child_metadata
            else:
                # Return cloned session
                return SessionMetadata(
                    session_id=sid,
                    status=SessionStatus.ACTIVE,
                    profile_name="foundation/base",
                    mount_plan_path=f"state/sessions/{sid}/mount_plan.json",
                    created_at=datetime.now(UTC),
                    started_at=datetime.now(UTC),
                    amplified_dir=".",
                    name="Parent Session (copy)" if created_sessions and sid == created_sessions[0] else "Child Session",
                )

        # list_sessions returns child when querying parent's subsessions
        def mock_list_sessions(parent_session_id=None, **kwargs):
            if parent_session_id == "parent_session":
                return [child_metadata]
            return []

        mock_session_state_service.create_session.side_effect = mock_create_session
        mock_session_state_service.get_session.side_effect = mock_get_session
        mock_session_state_service.list_sessions.side_effect = mock_list_sessions

        try:
            # Make request to clone parent
            response = client.post("/api/v1/sessions/parent_session/clone")

            # Assert response
            assert response.status_code == 201

            # Verify both parent and child were cloned (2 sessions created)
            assert len(created_sessions) == 2

            # Verify directories were created
            for session_id in created_sessions:
                assert (tmp_path / "sessions" / session_id).exists()
        finally:
            amplifierd.routers.sessions.get_state_dir = original_get_state_dir

    def test_clone_session_unexpected_error(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /api/v1/sessions/{session_id}/clone handles unexpected errors."""
        # Setup mock to raise exception during clone
        mock_session_state_service.get_session.side_effect = Exception("Unexpected clone error")

        # Make request
        response = client.post("/api/v1/sessions/test_session_123/clone")

        # Assert
        assert response.status_code == 500
        assert "Failed to clone session" in response.json()["detail"]
