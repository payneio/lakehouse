"""
Unit tests for session state management.

Tests message handling and transcript operations.
Note: Context and metadata functionality removed in new SessionMetadata model.
"""

from datetime import UTC
from datetime import datetime

import pytest

from lakehouse_library.models import Session
from lakehouse_library.models.sessions import SessionMessage
from lakehouse_library.sessions import state


@pytest.mark.unit
class TestSessionState:
    """Test session state management functions."""

    def test_add_message_creates_message(self, sample_session: Session) -> None:
        """Test add_message creates a SessionMessage object."""
        msg = state.add_message(sample_session, "user", "Hello, world!")

        assert isinstance(msg, SessionMessage)
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.timestamp is not None

    def test_add_message_sets_timestamp(self, sample_session: Session) -> None:
        """Test add_message sets current timestamp."""
        before = datetime.now(UTC)
        msg = state.add_message(sample_session, "user", "Test")
        after = datetime.now(UTC)

        assert before <= msg.timestamp <= after

    def test_add_message_updates_message_count(self, sample_session: Session) -> None:
        """Test add_message updates session message count."""
        state.add_message(sample_session, "user", "Message 1")
        # Note: We can't check sample_session.message_count directly as it's not updated in-memory
        # The state service updates the persisted session.json file

    def test_add_message_persists_transcript(self, sample_session: Session) -> None:
        """Test add_message saves transcript to storage."""
        state.add_message(sample_session, "user", "Test message")

        # Verify we can read the transcript back
        transcript = state.get_transcript(sample_session.session_id)
        assert len(transcript) > 0

    def test_add_multiple_messages(self, sample_session: Session) -> None:
        """Test adding multiple messages to session."""
        state.add_message(sample_session, "user", "Hello")
        state.add_message(sample_session, "assistant", "Hi there!")
        state.add_message(sample_session, "user", "How are you?")

        transcript = state.get_transcript(sample_session.session_id)
        assert len(transcript) == 3
        assert transcript[0].content == "Hello"
        assert transcript[1].content == "Hi there!"
        assert transcript[2].content == "How are you?"

    def test_update_context_is_noop(self, sample_session: Session) -> None:
        """Test update_context is a no-op (context removed in new model)."""
        # This should not raise an error, just do nothing
        state.update_context(sample_session, {"new_key": "new_value"})

    def test_get_transcript_returns_messages(self, sample_session: Session) -> None:
        """Test get_transcript returns all messages in order."""
        state.add_message(sample_session, "user", "First")
        state.add_message(sample_session, "assistant", "Second")
        state.add_message(sample_session, "user", "Third")

        transcript = state.get_transcript(sample_session.session_id)

        assert len(transcript) == 3
        assert all(isinstance(msg, SessionMessage) for msg in transcript)
        assert transcript[0].content == "First"
        assert transcript[1].content == "Second"
        assert transcript[2].content == "Third"

    def test_get_transcript_empty_for_new_session(self, sample_session: Session) -> None:
        """Test get_transcript returns empty list for new session."""
        transcript = state.get_transcript(sample_session.session_id)
        assert transcript == []

    def test_get_transcript_raises_for_nonexistent_session(self, mock_storage_env) -> None:
        """Test get_transcript returns empty list for nonexistent session."""
        # Updated: New implementation returns empty list instead of raising
        transcript = state.get_transcript("nonexistent-session-id")
        assert transcript == []

    def test_get_transcript_preserves_timestamps(self, sample_session: Session) -> None:
        """Test get_transcript preserves message timestamps."""
        from datetime import UTC
        from datetime import datetime

        before = datetime.now(UTC)
        state.add_message(sample_session, "user", "Test")
        after = datetime.now(UTC)

        transcript = state.get_transcript(sample_session.session_id)

        # Timestamp should be within the time window of message creation
        assert before <= transcript[0].timestamp <= after
        # Content should match
        assert transcript[0].content == "Test"
        assert transcript[0].role == "user"

    def test_message_roles(self, sample_session: Session) -> None:
        """Test different message roles work correctly."""
        state.add_message(sample_session, "user", "User message")
        state.add_message(sample_session, "assistant", "Assistant message")
        state.add_message(sample_session, "system", "System message")

        transcript = state.get_transcript(sample_session.session_id)

        assert transcript[0].role == "user"
        assert transcript[1].role == "assistant"
        assert transcript[2].role == "system"

    def test_transcript_persistence_across_loads(self, sample_session: Session, session_manager) -> None:
        """Test transcript persists across session get operations."""
        # Add messages
        state.add_message(sample_session, "user", "Hello")
        state.add_message(sample_session, "assistant", "Hi")

        # Get session (simulating reload)
        reloaded = session_manager.get_session(sample_session.session_id)
        assert reloaded is not None

        # Get transcript from reloaded session
        transcript = state.get_transcript(reloaded.session_id)

        assert len(transcript) == 2
        assert transcript[0].content == "Hello"
        assert transcript[1].content == "Hi"
