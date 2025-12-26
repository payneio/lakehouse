"""
Unit tests for SessionManager.

Tests session CRUD operations, persistence, and error handling.
"""

import uuid
from datetime import UTC
from datetime import datetime

import pytest

from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.sessions.manager import SessionManager


@pytest.mark.unit
class TestSessionManager:
    """Test SessionManager operations."""

    def test_create_session_with_explicit_id(self, session_manager: SessionManager) -> None:
        """Test create_session with explicit session ID."""
        session_id = str(uuid.uuid4())
        session = session_manager.create_session(session_id=session_id, profile_name="default")

        assert session.session_id == session_id
        assert session.profile_name == "default"

    def test_create_session_raises_on_duplicate_id(self, session_manager: SessionManager) -> None:
        """Test create_session raises error for duplicate session ID."""
        session_id = str(uuid.uuid4())
        session_manager.create_session(session_id=session_id, profile_name="default")

        with pytest.raises(ValueError, match="already exists"):
            session_manager.create_session(session_id=session_id, profile_name="default")

    def test_create_session_sets_profile(self, session_manager: SessionManager) -> None:
        """Test create_session sets the correct profile."""
        session = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="test-profile")
        assert session.profile_name == "test-profile"

    def test_create_session_sets_timestamps(self, session_manager: SessionManager) -> None:
        """Test create_session sets created_at timestamp."""
        before = datetime.now(UTC)
        session = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="default")
        after = datetime.now(UTC)

        assert before <= session.created_at <= after

    def test_create_session_initializes_message_count(self, session_manager: SessionManager) -> None:
        """Test create_session sets message_count to 0."""
        session = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="default")
        assert session.message_count == 0

    def test_create_session_persists_to_storage(self, session_manager: SessionManager) -> None:
        """Test create_session saves session to storage immediately."""
        session_id = str(uuid.uuid4())
        session_manager.create_session(session_id=session_id, profile_name="default")

        session_dir = session_manager.storage_dir / session_id
        assert session_dir.exists()
        assert (session_dir / "session.json").exists()
        assert (session_dir / "transcript.jsonl").exists()

    def test_get_session_loads_existing(self, session_manager: SessionManager, sample_session: SessionMetadata) -> None:
        """Test get_session loads an existing session."""
        loaded = session_manager.get_session(sample_session.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_session.session_id
        assert loaded.profile_name == sample_session.profile_name

    def test_get_session_returns_none_for_nonexistent(self, session_manager: SessionManager) -> None:
        """Test get_session returns None for nonexistent session."""
        result = session_manager.get_session("nonexistent-session-id")
        assert result is None

    def test_list_sessions_returns_all(self, session_manager: SessionManager) -> None:
        """Test list_sessions returns all created sessions."""
        session1 = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="profile1")
        session2 = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="profile2")

        sessions = session_manager.list_sessions()

        assert len(sessions) >= 2
        ids = [s.session_id for s in sessions]
        assert session1.session_id in ids
        assert session2.session_id in ids

    def test_list_sessions_sorted_by_created_at(self, session_manager: SessionManager) -> None:
        """Test list_sessions returns sessions sorted by created_at (newest first)."""
        session1 = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="first")
        session2 = session_manager.create_session(session_id=str(uuid.uuid4()), profile_name="second")

        sessions = session_manager.list_sessions()

        # Find our sessions in the list
        s1 = next(s for s in sessions if s.session_id == session1.session_id)
        s2 = next(s for s in sessions if s.session_id == session2.session_id)

        # Second session should come before first (newer)
        s1_index = sessions.index(s1)
        s2_index = sessions.index(s2)
        assert s2_index < s1_index

    def test_delete_session_removes_from_storage(
        self, session_manager: SessionManager, sample_session: SessionMetadata
    ) -> None:
        """Test delete_session removes session from storage."""
        session_dir = session_manager.storage_dir / sample_session.session_id
        assert session_dir.exists()

        result = session_manager.delete_session(sample_session.session_id)

        assert result is True
        assert not session_dir.exists()

    def test_delete_nonexistent_session_returns_false(self, session_manager: SessionManager) -> None:
        """Test delete_session returns False for nonexistent session."""
        result = session_manager.delete_session("nonexistent-id")
        assert result is False

    def test_append_message(self, session_manager: SessionManager, sample_session: SessionMetadata) -> None:
        """Test append_message adds message to transcript."""
        session_manager.append_message(session_id=sample_session.session_id, role="user", content="Hello, world!")

        # Verify message was appended by reading transcript
        transcript = session_manager.get_transcript(sample_session.session_id)
        assert len(transcript) == 1
        assert transcript[0].role == "user"
        assert transcript[0].content == "Hello, world!"

        # Verify message count updated
        session = session_manager.get_session(sample_session.session_id)
        assert session is not None
        assert session.message_count == 1

    def test_get_transcript(self, session_manager: SessionManager, sample_session: SessionMetadata) -> None:
        """Test get_transcript returns all messages."""
        session_manager.append_message(sample_session.session_id, "user", "Message 1")
        session_manager.append_message(sample_session.session_id, "assistant", "Message 2")

        transcript = session_manager.get_transcript(sample_session.session_id)

        assert len(transcript) == 2
        assert transcript[0].content == "Message 1"
        assert transcript[1].content == "Message 2"

    def test_get_transcript_with_limit(self, session_manager: SessionManager, sample_session: SessionMetadata) -> None:
        """Test get_transcript with limit returns last N messages."""
        for i in range(5):
            session_manager.append_message(sample_session.session_id, "user", f"Message {i}")

        transcript = session_manager.get_transcript(sample_session.session_id, limit=2)

        assert len(transcript) == 2
        assert transcript[0].content == "Message 3"
        assert transcript[1].content == "Message 4"

    def test_session_lifecycle(self, session_manager: SessionManager) -> None:
        """Test complete session lifecycle: create, append, load, delete."""
        # Create
        session_id = str(uuid.uuid4())
        session_manager.create_session(session_id=session_id, profile_name="lifecycle-test")

        # Verify exists
        session_dir = session_manager.storage_dir / session_id
        assert session_dir.exists()

        # Append message
        session_manager.append_message(session_id, "user", "Test message")

        # Load
        loaded = session_manager.get_session(session_id)
        assert loaded is not None
        assert loaded.message_count == 1

        # Delete
        session_manager.delete_session(session_id)
        assert not session_dir.exists()

    def test_delete_session_cascades_to_subsessions(self, session_manager: SessionManager) -> None:
        """Test delete_session also deletes all child subsessions."""
        # Create parent session
        parent_id = str(uuid.uuid4())
        session_manager.create_session(session_id=parent_id, profile_name="parent")

        # Create child subsessions
        child1_id = str(uuid.uuid4())
        child2_id = str(uuid.uuid4())
        session_manager.create_session(
            session_id=child1_id, profile_name="child1", parent_session_id=parent_id
        )
        session_manager.create_session(
            session_id=child2_id, profile_name="child2", parent_session_id=parent_id
        )

        # Verify all exist
        assert session_manager.get_session(parent_id) is not None
        assert session_manager.get_session(child1_id) is not None
        assert session_manager.get_session(child2_id) is not None

        # Delete parent
        result = session_manager.delete_session(parent_id)

        # All should be deleted
        assert result is True
        assert session_manager.get_session(parent_id) is None
        assert session_manager.get_session(child1_id) is None
        assert session_manager.get_session(child2_id) is None

    def test_delete_session_cascades_recursively(self, session_manager: SessionManager) -> None:
        """Test delete_session cascades through multiple levels of subsessions."""
        # Create grandparent -> parent -> child hierarchy
        grandparent_id = str(uuid.uuid4())
        parent_id = str(uuid.uuid4())
        child_id = str(uuid.uuid4())

        session_manager.create_session(session_id=grandparent_id, profile_name="grandparent")
        session_manager.create_session(
            session_id=parent_id, profile_name="parent", parent_session_id=grandparent_id
        )
        session_manager.create_session(
            session_id=child_id, profile_name="child", parent_session_id=parent_id
        )

        # Verify all exist
        assert session_manager.get_session(grandparent_id) is not None
        assert session_manager.get_session(parent_id) is not None
        assert session_manager.get_session(child_id) is not None

        # Delete grandparent
        result = session_manager.delete_session(grandparent_id)

        # All three levels should be deleted
        assert result is True
        assert session_manager.get_session(grandparent_id) is None
        assert session_manager.get_session(parent_id) is None
        assert session_manager.get_session(child_id) is None

    def test_delete_subsession_only_deletes_that_branch(self, session_manager: SessionManager) -> None:
        """Test deleting a subsession doesn't affect parent or siblings."""
        # Create parent with two children
        parent_id = str(uuid.uuid4())
        child1_id = str(uuid.uuid4())
        child2_id = str(uuid.uuid4())

        session_manager.create_session(session_id=parent_id, profile_name="parent")
        session_manager.create_session(
            session_id=child1_id, profile_name="child1", parent_session_id=parent_id
        )
        session_manager.create_session(
            session_id=child2_id, profile_name="child2", parent_session_id=parent_id
        )

        # Delete only child1
        result = session_manager.delete_session(child1_id)

        # child1 deleted, parent and child2 remain
        assert result is True
        assert session_manager.get_session(child1_id) is None
        assert session_manager.get_session(parent_id) is not None
        assert session_manager.get_session(child2_id) is not None
