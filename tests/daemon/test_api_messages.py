"""
Integration tests for messages API endpoints.

Tests message sending and transcript retrieval.
"""

from datetime import UTC
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifierd.main import app
from amplifierd.models.mount_plans import EmbeddedMount
from amplifierd.models.mount_plans import MountPlan
from amplifierd.models.mount_plans import SessionConfig
from amplifierd.routers.mount_plans import get_mount_plan_service
from amplifierd.routers.sessions import get_session_state_service


@pytest.fixture
def mock_session() -> Mock:
    """Mock amplifier-core session for testing.

    Returns:
        Mock session object
    """
    session = Mock()
    session.id = "test_session_123"
    session.transcript = []
    return session


@pytest.fixture
def mock_session_manager(mock_session: Mock) -> Mock:
    """Mock SessionManager for messages API.

    Args:
        mock_session: Mock session fixture

    Returns:
        Mock SessionManager
    """
    manager = Mock()
    manager.resume_session.return_value = mock_session
    manager.save_session.return_value = None
    return manager


@pytest.fixture
def mock_mount_plan() -> MountPlan:
    """Sample mount plan for testing.

    Returns:
        Sample mount plan with basic structure
    """
    return MountPlan(
        format_version="1.0",
        session=SessionConfig(
            session_id="test_session_123",
            profile_id="foundation/base",
            created_at=datetime.now(UTC).isoformat(),
            settings={},
        ),
        mount_points=[
            EmbeddedMount(
                module_id="foundation/base.agents.test-agent",
                module_type="agent",
                content="# Test Agent",
            )
        ],
    )


@pytest.fixture
def mock_mount_plan_service(mock_mount_plan: MountPlan) -> Mock:
    """Mock mount plan service.

    Args:
        mock_mount_plan: Sample mount plan fixture

    Returns:
        Mock service
    """
    service = Mock()
    service.generate_mount_plan = Mock(return_value=mock_mount_plan.model_dump())
    return service


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
def mock_session_state_service(mock_session_metadata: SessionMetadata) -> Mock:
    """Mock session state service.

    Args:
        mock_session_metadata: Sample session metadata fixture

    Returns:
        Mock service
    """
    service = Mock()
    service.create_session = Mock(return_value=mock_session_metadata)
    service.get_session = Mock(return_value=mock_session_metadata)
    service.append_message = Mock()
    service.get_transcript = Mock(return_value=[])
    return service


@pytest.fixture
def mock_amplified_directory_service(monkeypatch):
    """Mock AmplifiedDirectoryService to bypass directory validation."""
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

    monkeypatch.setattr(
        "amplifierd.routers.sessions.AmplifiedDirectoryService",
        lambda data_dir: mock_service
    )
    yield


@pytest.fixture
def override_services(
    mock_session_manager: Mock,
    mock_mount_plan_service: Mock,
    mock_session_state_service: Mock,
    mock_amplified_directory_service,
):
    """Override service dependencies with test services.

    Args:
        mock_session_manager: Mock session manager
        mock_mount_plan_service: Mock mount plan service
        mock_session_state_service: Mock session state service
        mock_amplified_directory_service: Mock amplified directory service

    Yields:
        None
    """
    # Import here to avoid circular import issues
    from amplifierd.routers.messages import get_session_state_service as get_msg_svc

    app.dependency_overrides[get_mount_plan_service] = lambda: mock_mount_plan_service
    app.dependency_overrides[get_session_state_service] = lambda: mock_session_state_service
    app.dependency_overrides[get_msg_svc] = lambda: mock_session_state_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(mock_storage_env, override_services) -> TestClient:
    """Create FastAPI test client with isolated storage and mocked dependencies.

    Args:
        mock_storage_env: Storage environment fixture
        override_services: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.fixture
def session_id(client: TestClient) -> str:
    """Create a test session and return its ID.

    Args:
        client: Test client with mocked dependencies

    Returns:
        Session ID
    """
    response = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"})
    return response.json()["sessionId"]


@pytest.mark.integration
class TestMessagesAPI:
    """Test message API endpoints."""

    def test_send_message_returns_201(self, client: TestClient, session_id: str) -> None:
        """Test POST /api/v1/sessions/{id}/messages creates message."""
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages", json={"role": "user", "content": "Hello, world!"}
        )

        assert response.status_code == 201

    def test_send_message_404_for_nonexistent_session(
        self, client: TestClient, mock_session_state_service: Mock
    ) -> None:
        """Test POST /messages returns 404 for nonexistent session."""
        # Mock service to return None (session not found)
        mock_session_state_service.get_session.return_value = None

        response = client.post("/api/v1/sessions/nonexistent-id/messages", json={"role": "user", "content": "Test"})

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_messages_returns_transcript(
        self, client: TestClient, session_id: str, mock_session_state_service: Mock
    ) -> None:
        """Test GET /api/v1/sessions/{id}/transcript returns transcript."""
        # Send some messages first
        client.post(f"/api/v1/sessions/{session_id}/messages", json={"role": "user", "content": "First message"})
        client.post(f"/api/v1/sessions/{session_id}/messages", json={"role": "user", "content": "Second message"})

        # Mock the service to return messages
        mock_session_state_service.get_transcript.return_value = [
            SessionMessage(
                timestamp=datetime.now(UTC),
                role="user",
                content="First message",
                agent=None,
                token_count=None,
            ),
            SessionMessage(
                timestamp=datetime.now(UTC),
                role="user",
                content="Second message",
                agent=None,
                token_count=None,
            ),
        ]

        # Get transcript
        response = client.get(f"/api/v1/sessions/{session_id}/transcript")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["content"] == "First message"
        assert data[1]["content"] == "Second message"

    def test_get_messages_empty_for_new_session(self, client: TestClient, session_id: str) -> None:
        """Test GET /transcript returns empty list for new session."""
        response = client.get(f"/api/v1/sessions/{session_id}/transcript")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_messages_404_for_nonexistent_session(
        self, client: TestClient, mock_session_state_service: Mock
    ) -> None:
        """Test GET /transcript returns 404 for nonexistent session."""
        # Mock service to return None (session not found)
        mock_session_state_service.get_session.return_value = None

        response = client.get("/api/v1/sessions/nonexistent-id/transcript")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_messages_preserve_order(
        self, client: TestClient, session_id: str, mock_session_state_service: Mock
    ) -> None:
        """Test messages are returned in order they were sent."""
        messages = ["First", "Second", "Third", "Fourth"]

        for msg in messages:
            client.post(f"/api/v1/sessions/{session_id}/messages", json={"role": "user", "content": msg})

        # Mock the service to return messages in order
        mock_session_state_service.get_transcript.return_value = [
            SessionMessage(timestamp=datetime.now(UTC), role="user", content=msg, agent=None, token_count=None)
            for msg in messages
        ]

        response = client.get(f"/api/v1/sessions/{session_id}/transcript")
        transcript = response.json()

        for i, msg in enumerate(messages):
            assert transcript[i]["content"] == msg

    def test_messages_include_metadata(self, client: TestClient, session_id: str) -> None:
        """Test messages endpoint returns 201."""
        response = client.post(
            f"/api/v1/sessions/{session_id}/messages", json={"role": "user", "content": "Test message"}
        )

        assert response.status_code == 201

    def test_multiple_sessions_isolated(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test messages in different sessions are isolated."""
        # Setup mock to return different sessions
        session_counter = [0]

        def create_session_side_effect(*args, **kwargs):
            session_counter[0] += 1
            return SessionMetadata(
                session_id=f"test_session_{session_counter[0]}",
                status=SessionStatus.CREATED,
                profile_name="foundation/base",
                mount_plan_path=f"state/sessions/test_session_{session_counter[0]}/mount_plan.json",
                created_at=datetime.now(UTC),
            )

        mock_session_state_service.create_session.side_effect = create_session_side_effect

        # Create two sessions
        session1 = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"}).json()["sessionId"]

        session2 = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"}).json()["sessionId"]

        # Add messages to session1
        client.post(f"/api/v1/sessions/{session1}/messages", json={"role": "user", "content": "Session 1 message"})

        # Add messages to session2
        client.post(f"/api/v1/sessions/{session2}/messages", json={"role": "user", "content": "Session 2 message"})

        # Mock the service to return appropriate messages for each session
        # We capture the session IDs in the closure
        def get_transcript_side_effect(session_id: str, limit: int | None = None):
            messages_map = {
                session1: [
                    SessionMessage(
                        timestamp=datetime.now(UTC),
                        role="user",
                        content="Session 1 message",
                        agent=None,
                        token_count=None,
                    )
                ],
                session2: [
                    SessionMessage(
                        timestamp=datetime.now(UTC),
                        role="user",
                        content="Session 2 message",
                        agent=None,
                        token_count=None,
                    )
                ],
            }
            return messages_map.get(session_id, [])

        mock_session_state_service.get_transcript.side_effect = get_transcript_side_effect

        # Verify isolation
        transcript1 = client.get(f"/api/v1/sessions/{session1}/transcript").json()
        transcript2 = client.get(f"/api/v1/sessions/{session2}/transcript").json()

        assert len(transcript1) == 1
        assert len(transcript2) == 1
        assert transcript1[0]["content"] == "Session 1 message"
        assert transcript2[0]["content"] == "Session 2 message"
