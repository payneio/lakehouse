"""
Unit tests for execution runner.

Tests ExecutionRunner with mocked amplifier-core to avoid real LLM calls.
"""

import pytest
from unittest.mock import Mock

from amplifier_library.execution.runner import ExecutionRunner
from amplifier_library.models import Session
from amplifier_library.sessions import state


@pytest.fixture
def mock_session_manager() -> Mock:
    """Create mock SessionManager."""
    session_manager = Mock()
    session_manager.get_transcript = Mock(return_value=[])
    return session_manager


@pytest.fixture
def mock_resolver() -> Mock:
    """Create mock BundleModuleResolver."""
    resolver = Mock()
    resolver.async_resolve = Mock()
    return resolver


@pytest.mark.unit
class TestExecutionRunner:
    """Test ExecutionRunner operations."""

    def test_execution_runner_init(self, mock_session_manager: Mock, mock_resolver: Mock) -> None:
        """Test ExecutionRunner initialization."""
        config = {"model": "gpt-4"}
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config=config,
            session_id="test-session",
            resolver=mock_resolver,
        )

        assert runner.config == config
        assert runner._session is None

    @pytest.mark.asyncio
    async def test_execute_adds_user_message(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test execute adds user message to session state."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        await runner.execute(sample_session, "Hello")

        transcript = state.get_transcript(sample_session.session_id)
        assert len(transcript) >= 1
        assert transcript[0].role == "user"
        assert transcript[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_execute_adds_assistant_response(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test execute adds assistant response to session state."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        response = await runner.execute(sample_session, "Test prompt")

        assert isinstance(response, str)
        assert len(response) > 0

        # Check transcript has both messages
        transcript = state.get_transcript(sample_session.session_id)
        assert len(transcript) == 2
        assert transcript[0].role == "user"
        assert transcript[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_execute_returns_response(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test execute returns the assistant's response."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        response = await runner.execute(sample_session, "Test")

        assert "mocked response" in response.lower()

    @pytest.mark.asyncio
    async def test_execute_creates_amplifier_session_once(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test execute creates AmplifierSession only once."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        assert runner._session is None

        await runner.execute(sample_session, "First")
        first_session = runner._session

        await runner.execute(sample_session, "Second")
        second_session = runner._session

        # Should reuse the same session
        assert first_session is second_session

    @pytest.mark.asyncio
    async def test_execute_handles_missing_amplifier_core(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, monkeypatch
    ) -> None:
        """Test execute raises helpful error if amplifier-core not installed."""
        # Remove the mock module
        import sys

        if "amplifier_core" in sys.modules:
            monkeypatch.delitem(sys.modules, "amplifier_core")
        if "amplifier" in sys.modules:
            monkeypatch.delitem(sys.modules, "amplifier")

        # Mock the import to raise ImportError
        original_import = __import__

        def mock_import(name, *args, **kwargs):
            if name == "amplifier_core":
                raise ImportError("No module named 'amplifier_core'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)

        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        with pytest.raises(RuntimeError, match="amplifier-core is required"):
            await runner.execute(sample_session, "Test")

    @pytest.mark.asyncio
    async def test_execute_handles_execution_error(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test execute handles errors during execution gracefully."""

        # Create a mock that raises an error
        class FailingSession:
            async def initialize(self):
                # No initialization needed for mock
                return None

            async def execute(self, prompt):
                raise ValueError("Simulated execution error")

        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )
        runner._session = FailingSession()  # type: ignore[assignment]

        response = await runner.execute(sample_session, "Test")

        # Should return error message instead of crashing
        assert "error" in response.lower()

        # Should add error to transcript
        transcript = state.get_transcript(sample_session.session_id)
        assert any("error" in msg.content.lower() for msg in transcript)

    @pytest.mark.asyncio
    async def test_cleanup_clears_session(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test cleanup clears the internal AmplifierSession."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        await runner.execute(sample_session, "Test")
        assert runner._session is not None

        await runner.cleanup()
        assert runner._session is None

    @pytest.mark.asyncio
    async def test_multiple_executions_update_transcript(
        self, sample_session: Session, mock_session_manager: Mock, mock_resolver: Mock, mock_amplifier_module
    ) -> None:
        """Test multiple executions build up the transcript."""
        runner = ExecutionRunner(
            session_manager=mock_session_manager,
            config={},
            session_id="test-session",
            resolver=mock_resolver,
        )

        await runner.execute(sample_session, "First question")
        await runner.execute(sample_session, "Second question")
        await runner.execute(sample_session, "Third question")

        transcript = state.get_transcript(sample_session.session_id)

        # Should have 6 messages: 3 user + 3 assistant
        assert len(transcript) == 6

        # Verify order
        assert transcript[0].content == "First question"
        assert transcript[2].content == "Second question"
        assert transcript[4].content == "Third question"
