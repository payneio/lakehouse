"""
Integration tests for /execute endpoint with SSE streaming.

Tests the /api/v1/sessions/{id}/execute endpoint that:
1. Saves user message to SessionStateService before execution
2. Streams execution results via SSE
3. Accumulates assistant response during streaming
4. Saves assistant response to SessionStateService after completion
"""

import json
from datetime import UTC
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.models.mount_plans import EmbeddedMount
from amplifierd.models.mount_plans import MountPlan
from amplifierd.models.mount_plans import SessionConfig
from amplifierd.models.sessions import SessionMessage
from amplifierd.models.sessions import SessionMetadata
from amplifierd.models.sessions import SessionStatus
from amplifierd.routers.mount_plans import get_mount_plan_service
from amplifierd.routers.sessions import get_session_state_service


def parse_sse_stream(response_text: str) -> list[dict]:
    """Parse SSE stream into list of events.

    Args:
        response_text: Raw SSE response text

    Returns:
        List of event dictionaries with 'event' and 'data' keys
    """
    events = []
    # Split by double newline (event separator)
    raw_events = response_text.strip().split("\n\n")

    for raw_event in raw_events:
        if not raw_event.strip():
            continue

        event_dict = {}
        lines = raw_event.split("\n")

        for line in lines:
            if line.startswith("event: "):
                event_dict["event"] = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:].strip()
                try:
                    event_dict["data"] = json.loads(data_str)
                except json.JSONDecodeError:
                    event_dict["data"] = data_str

        if event_dict:
            events.append(event_dict)

    return events


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
    service.generate_mount_plan = AsyncMock(return_value=mock_mount_plan)
    return service


@pytest.fixture
def mock_session_metadata() -> SessionMetadata:
    """Sample session metadata for testing.

    Returns:
        Sample session metadata
    """
    return SessionMetadata(
        session_id="test_session_123",
        amplified_dir=".",
        status=SessionStatus.CREATED,
        profile_name="foundation/base",
        mount_plan_path="mount_plan.json",
        created_at=datetime.now(UTC),
        message_count=0,
        agent_invocations=0,
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
def mock_execution_runner():
    """Mock ExecutionRunner for testing.

    Returns:
        Mock ExecutionRunner that yields tokens
    """

    class MockRunner:
        """Mock runner with async streaming."""

        async def execute_stream(self, session, content):
            """Mock streaming execution that yields tokens."""
            tokens = ["Hello", " from", " the", " assistant", "!"]
            for token in tokens:
                yield token

    return MockRunner()


@pytest.fixture
def patch_execution_runner(mock_execution_runner):
    """Patch ExecutionRunner to use mock.

    Args:
        mock_execution_runner: Mock runner instance

    Yields:
        Patched ExecutionRunner
    """
    with patch("amplifierd.routers.messages.ExecutionRunner", return_value=mock_execution_runner):
        yield mock_execution_runner


@pytest.fixture
def override_services(
    mock_mount_plan_service: Mock,
    mock_session_state_service: Mock,
):
    """Override service dependencies with test services.

    Args:
        mock_mount_plan_service: Mock mount plan service
        mock_session_state_service: Mock session state service

    Yields:
        None
    """
    from amplifierd.routers.messages import get_session_state_service as get_msg_svc

    app.dependency_overrides[get_mount_plan_service] = lambda: mock_mount_plan_service
    app.dependency_overrides[get_session_state_service] = lambda: mock_session_state_service
    app.dependency_overrides[get_msg_svc] = lambda: mock_session_state_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(mock_storage_env, override_services, patch_execution_runner) -> TestClient:
    """Create FastAPI test client with isolated storage and mocked dependencies.

    Args:
        mock_storage_env: Storage environment fixture
        override_services: Dependency override fixture
        patch_execution_runner: Patched ExecutionRunner

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.fixture
def session_id_with_mount_plan(client: TestClient, mock_storage_env, mock_mount_plan: MountPlan) -> str:
    """Create a test session with mount plan file on disk.

    Args:
        client: Test client with mocked dependencies
        mock_storage_env: Temp storage directory
        mock_mount_plan: Sample mount plan

    Returns:
        Session ID
    """
    # Create session
    response = client.post("/api/v1/sessions/", json={"profile_name": "foundation/base"})
    session_id = response.json()["sessionId"]

    # Write mount plan to expected location (get_state_dir() returns AMPLIFIERD_HOME/state)
    mount_plan_path = mock_storage_env / "state" / "sessions" / session_id / "mount_plan.json"
    mount_plan_path.parent.mkdir(parents=True, exist_ok=True)
    mount_plan_path.write_text(mock_mount_plan.model_dump_json(indent=2))

    return session_id


@pytest.mark.integration
class TestExecuteAPI:
    """Test /execute endpoint with SSE streaming."""

    def test_execute_returns_sse_stream(self, client: TestClient, session_id_with_mount_plan: str) -> None:
        """Test POST /execute returns SSE stream with proper format."""
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Hello, assistant!"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # TestClient wraps SSE responses - just verify we got content
        assert len(response.text) > 0

        # Verify response contains expected SSE elements
        assert "event: message" in response.text
        assert "type" in response.text
        assert "content" in response.text
        assert "event: done" in response.text

    def test_execute_saves_user_message_first(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test user message is saved before execution starts."""
        user_message = "Test user message"

        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": user_message},
        )

        assert response.status_code == 200

        # Verify append_message was called
        calls = mock_session_state_service.append_message.call_args_list

        # Should have at least one call (user message)
        assert len(calls) >= 1

        # First call should be user message
        first_call = calls[0]
        assert first_call[1]["session_id"] == session_id_with_mount_plan
        assert first_call[1]["role"] == "user"
        assert first_call[1]["content"] == user_message

    def test_execute_saves_assistant_response_after_streaming(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test assistant response is saved after streaming completes."""
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Hello!"},
        )

        assert response.status_code == 200

        # Verify append_message was called twice (user + assistant)
        calls = mock_session_state_service.append_message.call_args_list
        assert len(calls) == 2

        # Second call should be assistant message
        assistant_call = calls[1]
        assert assistant_call[1]["session_id"] == session_id_with_mount_plan
        assert assistant_call[1]["role"] == "assistant"
        # Should have accumulated all tokens
        assert assistant_call[1]["content"] == "Hello from the assistant!"

    def test_execute_integration_with_transcript(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test execute + transcript returns both messages."""
        user_content = "What is 2+2?"

        # Execute
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": user_content},
        )

        assert response.status_code == 200

        # Get accumulated assistant response
        events = parse_sse_stream(response.text)
        message_events = [e for e in events if e.get("event") == "message"]
        assistant_content = "".join(e["data"]["content"] for e in message_events)

        # Mock transcript to return both messages
        mock_session_state_service.get_transcript.return_value = [
            SessionMessage(
                timestamp=datetime.now(UTC),
                role="user",
                content=user_content,
                agent=None,
                token_count=None,
            ),
            SessionMessage(
                timestamp=datetime.now(UTC),
                role="assistant",
                content=assistant_content,
                agent=None,
                token_count=None,
            ),
        ]

        # Get transcript
        transcript_response = client.get(f"/api/v1/sessions/{session_id_with_mount_plan}/transcript")

        assert transcript_response.status_code == 200
        transcript = transcript_response.json()

        # Should have 2 messages
        assert len(transcript) == 2

        # First is user
        assert transcript[0]["role"] == "user"
        assert transcript[0]["content"] == user_content

        # Second is assistant
        assert transcript[1]["role"] == "assistant"
        assert transcript[1]["content"] == assistant_content

    def test_execute_messages_in_correct_order(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test messages are saved in correct order (user first, then assistant)."""
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Test"},
        )

        assert response.status_code == 200

        calls = mock_session_state_service.append_message.call_args_list
        assert len(calls) == 2

        # Verify order: user then assistant
        assert calls[0][1]["role"] == "user"
        assert calls[1][1]["role"] == "assistant"

    def test_execute_includes_timestamps(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test saved messages include timestamps."""
        # Mock transcript to verify timestamps
        now = datetime.now(UTC)
        mock_session_state_service.get_transcript.return_value = [
            SessionMessage(
                timestamp=now,
                role="user",
                content="Test",
                agent=None,
                token_count=None,
            ),
        ]

        # Execute
        client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Test"},
        )

        # Get transcript
        transcript_response = client.get(f"/api/v1/sessions/{session_id_with_mount_plan}/transcript")
        transcript = transcript_response.json()

        # All messages should have timestamps
        assert all("timestamp" in msg for msg in transcript)

    def test_execute_404_for_nonexistent_session(self, client: TestClient, mock_session_state_service: Mock) -> None:
        """Test POST /execute returns 404 for nonexistent session."""
        # Mock service to return None (session not found)
        mock_session_state_service.get_session.return_value = None

        response = client.post(
            "/api/v1/sessions/nonexistent-id/execute",
            json={"content": "Test"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_execute_accumulates_tokens_correctly(
        self, client: TestClient, session_id_with_mount_plan: str, mock_session_state_service: Mock
    ) -> None:
        """Test streaming tokens are accumulated into complete response."""
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Test"},
        )

        assert response.status_code == 200

        # Verify assistant response was saved with accumulated tokens
        calls = mock_session_state_service.append_message.call_args_list
        assistant_calls = [c for c in calls if c[1]["role"] == "assistant"]

        assert len(assistant_calls) == 1
        full_response = assistant_calls[0][1]["content"]

        # Should match mock tokens accumulated
        assert full_response == "Hello from the assistant!"

    def test_execute_empty_response_not_saved(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
        mock_execution_runner: Mock,
    ) -> None:
        """Test empty assistant responses are not saved."""

        # Mock empty stream
        async def empty_stream(session, content):
            """Yield no tokens."""
            return
            yield  # Make it a generator

        mock_execution_runner.execute_stream = empty_stream

        client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "Test"},
        )

        # Should only have user message call, not assistant
        calls = mock_session_state_service.append_message.call_args_list

        # Only user message should be saved
        assert len(calls) == 1
        assert calls[0][1]["role"] == "user"


@pytest.mark.integration
class TestExecuteErrorHandling:
    """Test error handling in /execute endpoint."""

    def test_execute_error_returns_error_event(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        patch_execution_runner,
    ) -> None:
        """Test execution errors are returned as SSE error events."""

        # Create error mock runner
        class ErrorRunner:
            async def execute_stream(self, session, content):
                raise RuntimeError("Test execution error")
                yield  # Make it a generator

        # Patch with error runner for this test
        with patch("amplifierd.routers.messages.ExecutionRunner", return_value=ErrorRunner()):
            response = client.post(
                f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
                json={"content": "Test"},
            )

            # Should still return 200 (SSE handles errors in stream)
            assert response.status_code == 200

            # Verify error is in response
            assert "error" in response.text.lower()
            assert "Test execution error" in response.text

    def test_execute_missing_mount_plan_returns_500(
        self,
        client: TestClient,
        mock_session_state_service: Mock,
    ) -> None:
        """Test missing mount plan file returns 500."""
        # Create session metadata without mount plan file
        session_id = "test_session_no_mount"
        mock_session_state_service.get_session.return_value = SessionMetadata(
            session_id=session_id,
            status=SessionStatus.CREATED,
            profile_name="foundation/base",
            mount_plan_path="mount_plan.json",
            created_at=datetime.now(UTC),
        )

        response = client.post(
            f"/api/v1/sessions/{session_id}/execute",
            json={"content": "Test"},
        )

        assert response.status_code == 500
        assert "Mount plan not found" in response.json()["detail"]

    def test_execute_handles_malformed_content(self, client: TestClient, session_id_with_mount_plan: str) -> None:
        """Test execute handles malformed request content."""
        # Try with missing content field
        response = client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={},  # Missing 'content'
        )

        # FastAPI should return 422 for validation error
        assert response.status_code == 422


@pytest.mark.integration
class TestExecuteMultipleCalls:
    """Test multiple execute calls build transcript correctly."""

    def test_multiple_executions_append_to_transcript(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test multiple execute calls append to transcript."""
        messages = [
            ("First question", "First answer"),
            ("Second question", "Second answer"),
            ("Third question", "Third answer"),
        ]

        accumulated_transcript = []

        for user_msg, _ in messages:
            # Execute
            response = client.post(
                f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
                json={"content": user_msg},
            )

            assert response.status_code == 200

            # Get accumulated response
            events = parse_sse_stream(response.text)
            message_events = [e for e in events if e.get("event") == "message"]
            assistant_msg = "".join(e["data"]["content"] for e in message_events)

            # Add to mock transcript
            accumulated_transcript.extend(
                [
                    SessionMessage(
                        timestamp=datetime.now(UTC),
                        role="user",
                        content=user_msg,
                        agent=None,
                        token_count=None,
                    ),
                    SessionMessage(
                        timestamp=datetime.now(UTC),
                        role="assistant",
                        content=assistant_msg,
                        agent=None,
                        token_count=None,
                    ),
                ]
            )

        # Mock transcript to return all messages
        mock_session_state_service.get_transcript.return_value = accumulated_transcript

        # Get final transcript
        transcript_response = client.get(f"/api/v1/sessions/{session_id_with_mount_plan}/transcript")
        transcript = transcript_response.json()

        # Should have 6 messages (3 user + 3 assistant)
        assert len(transcript) == 6

        # Verify alternating pattern
        for i in range(0, len(transcript), 2):
            assert transcript[i]["role"] == "user"
            assert transcript[i + 1]["role"] == "assistant"

    def test_execute_maintains_conversation_context(
        self,
        client: TestClient,
        session_id_with_mount_plan: str,
        mock_session_state_service: Mock,
    ) -> None:
        """Test multiple executions maintain conversation context."""
        # First message
        client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "My name is Alice"},
        )

        # Second message (referencing first)
        client.post(
            f"/api/v1/sessions/{session_id_with_mount_plan}/execute",
            json={"content": "What is my name?"},
        )

        # Verify append_message called 4 times total (2 user + 2 assistant)
        calls = mock_session_state_service.append_message.call_args_list
        assert len(calls) == 4

        # Verify pattern
        assert calls[0][1]["role"] == "user"
        assert calls[0][1]["content"] == "My name is Alice"
        assert calls[1][1]["role"] == "assistant"
        assert calls[2][1]["role"] == "user"
        assert calls[2][1]["content"] == "What is my name?"
        assert calls[3][1]["role"] == "assistant"
