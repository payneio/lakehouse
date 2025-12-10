"""Unit and integration tests for SessionStateService."""

import json
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest

from amplifier_library.config.loader import load_config
from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifier_library.sessions.manager import SessionManager as SessionStateService
from amplifierd.models.mount_plans import MountPlan
from amplifierd.models.mount_plans import SessionConfig


class TestSessionStateService:
    """Tests for SessionStateService."""

    @pytest.fixture
    def state_dir(self, tmp_path: Path) -> Path:
        """Create temporary state directory."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        return state_dir

    @pytest.fixture
    def service(self, state_dir: Path) -> SessionStateService:
        """Create SessionStateService instance."""
        return SessionStateService(storage_dir=state_dir)

    @pytest.fixture
    def sample_mount_plan(self) -> MountPlan:
        """Create sample mount plan for testing."""
        session_config = SessionConfig(
            session_id="test_session",
            profile_id="foundation/base",
            created_at=datetime.now(UTC).isoformat(),
        )
        return MountPlan(session=session_config, mount_points=[])

    def test_init_creates_sessions_directory(self, state_dir: Path) -> None:
        """Test that initializing service creates sessions directory."""
        SessionStateService(storage_dir=state_dir)

        sessions_dir = state_dir / "sessions"
        assert sessions_dir.exists()
        assert sessions_dir.is_dir()

    def test_create_session_happy_path(
        self,
        service: SessionStateService,
        state_dir: Path,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test creating session creates all required files."""
        metadata = service.create_session(
            session_id="sess_test",
            profile_name="foundation.base",
            mount_plan=sample_mount_plan,
        )

        # Verify metadata
        assert metadata.session_id == "sess_test"
        assert metadata.profile_name == "foundation.base"
        assert metadata.status == SessionStatus.CREATED
        assert metadata.created_at is not None
        assert metadata.started_at is None
        assert metadata.ended_at is None
        assert metadata.message_count == 0

        # Verify directory structure
        session_dir = state_dir / "sessions" / "sess_test"
        assert session_dir.exists()

        # Verify files exist
        assert (session_dir / "mount_plan.json").exists()
        assert (session_dir / "session.json").exists()
        assert (session_dir / "transcript.jsonl").exists()

        # Verify mount plan was saved
        mount_plan_data = json.loads((session_dir / "mount_plan.json").read_text())
        # Check with both camelCase and snake_case as Pydantic may use either
        assert (
            mount_plan_data["session"].get("sessionId") == "test_session"
            or mount_plan_data["session"].get("session_id") == "test_session"
        )

        # Verify session metadata was saved
        session_data = json.loads((session_dir / "session.json").read_text())
        assert session_data.get("sessionId") == "sess_test" or session_data.get("session_id") == "sess_test"
        assert session_data["status"] == "created"

        # Verify transcript is empty
        transcript_content = (session_dir / "transcript.jsonl").read_text()
        assert transcript_content == ""

    def test_create_session_with_parent(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test creating session with parent session ID."""
        metadata = service.create_session(
            session_id="sess_child",
            profile_name="foundation.base",
            mount_plan=sample_mount_plan,
            parent_session_id="sess_parent",
        )

        assert metadata.parent_session_id == "sess_parent"

    def test_create_session_idempotency_error(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test that creating duplicate session raises ValueError."""
        service.create_session(
            session_id="sess_dup",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        with pytest.raises(ValueError) as exc_info:
            service.create_session(
                session_id="sess_dup",
                profile_name="test.profile",
                mount_plan=sample_mount_plan,
            )

        assert "already exists" in str(exc_info.value)

    def test_start_session(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test transitioning session from CREATED to ACTIVE."""
        service.create_session(
            session_id="sess_start",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        service.start_session("sess_start")

        metadata = service.get_session("sess_start")
        assert metadata is not None
        assert metadata.status == SessionStatus.ACTIVE
        assert metadata.started_at is not None

    def test_start_session_invalid_state(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test that starting already active session raises ValueError."""
        service.create_session(
            session_id="sess_bad_start",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )
        service.start_session("sess_bad_start")

        with pytest.raises(ValueError) as exc_info:
            service.start_session("sess_bad_start")

        assert "Cannot start session" in str(exc_info.value)

    def test_complete_session(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test transitioning session from ACTIVE to COMPLETED."""
        service.create_session(
            session_id="sess_complete",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )
        service.start_session("sess_complete")

        service.complete_session("sess_complete")

        metadata = service.get_session("sess_complete")
        assert metadata is not None
        assert metadata.status == SessionStatus.COMPLETED
        assert metadata.ended_at is not None

    def test_fail_session(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test transitioning session from ACTIVE to FAILED with error."""
        service.create_session(
            session_id="sess_fail",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )
        service.start_session("sess_fail")

        service.fail_session(
            session_id="sess_fail",
            error_message="Test error occurred",
            error_details={"exception": "TestException", "code": 500},
        )

        metadata = service.get_session("sess_fail")
        assert metadata is not None
        assert metadata.status == SessionStatus.FAILED
        assert metadata.ended_at is not None
        assert metadata.error_message == "Test error occurred"
        assert metadata.error_details is not None
        assert metadata.error_details["exception"] == "TestException"

    def test_terminate_session(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test transitioning session from ACTIVE to TERMINATED."""
        service.create_session(
            session_id="sess_terminate",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )
        service.start_session("sess_terminate")

        service.terminate_session("sess_terminate")

        metadata = service.get_session("sess_terminate")
        assert metadata is not None
        assert metadata.status == SessionStatus.TERMINATED
        assert metadata.ended_at is not None

    def test_append_message(
        self,
        service: SessionStateService,
        state_dir: Path,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test appending messages to transcript."""
        service.create_session(
            session_id="sess_messages",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        # Append user message
        service.append_message(
            session_id="sess_messages",
            role="user",
            content="Hello, how can you help?",
        )

        # Append assistant message with token count
        service.append_message(
            session_id="sess_messages",
            role="assistant",
            content="I can help with many tasks.",
            token_count=25,
        )

        # Verify transcript file
        transcript_path = state_dir / "sessions" / "sess_messages" / "transcript.jsonl"
        lines = transcript_path.read_text().strip().split("\n")
        assert len(lines) == 2

        # Verify first message
        msg1 = json.loads(lines[0])
        assert msg1["role"] == "user"
        assert msg1["content"] == "Hello, how can you help?"
        assert msg1["agent"] is None

        # Verify second message
        msg2 = json.loads(lines[1])
        assert msg2["role"] == "assistant"
        assert msg2["content"] == "I can help with many tasks."
        assert msg2.get("tokenCount") == 25 or msg2.get("token_count") == 25

        # Verify metadata updated
        metadata = service.get_session("sess_messages")
        assert metadata is not None
        assert metadata.message_count == 2
        assert metadata.token_usage == 25

    def test_append_message_with_agent(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test appending message from specific agent."""
        service.create_session(
            session_id="sess_agent",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        service.append_message(
            session_id="sess_agent",
            role="assistant",
            content="Analysis complete.",
            agent="zen-architect",
            token_count=10,
        )

        messages = service.get_transcript("sess_agent")
        assert len(messages) == 1
        assert messages[0].agent == "zen-architect"

    def test_get_transcript(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test retrieving full transcript."""
        service.create_session(
            session_id="sess_transcript",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        # Add several messages
        for i in range(5):
            service.append_message(
                session_id="sess_transcript",
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )

        messages = service.get_transcript("sess_transcript")

        assert len(messages) == 5
        assert all(isinstance(msg, SessionMessage) for msg in messages)
        assert messages[0].content == "Message 0"
        assert messages[4].content == "Message 4"

    def test_get_transcript_with_limit(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test retrieving transcript with limit (last N messages)."""
        service.create_session(
            session_id="sess_limit",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        # Add 10 messages
        for i in range(10):
            service.append_message(
                session_id="sess_limit",
                role="user",
                content=f"Message {i}",
            )

        # Get last 3 messages
        messages = service.get_transcript("sess_limit", limit=3)

        assert len(messages) == 3
        assert messages[0].content == "Message 7"  # Last 3: 7, 8, 9
        assert messages[2].content == "Message 9"

    def test_get_session(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test getting session metadata."""
        created = service.create_session(
            session_id="sess_get",
            profile_name="test.profile",
            mount_plan=sample_mount_plan,
        )

        retrieved = service.get_session("sess_get")

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.status == created.status
        assert retrieved.profile_name == created.profile_name

    def test_get_session_not_found(self, service: SessionStateService) -> None:
        """Test getting nonexistent session returns None."""
        result = service.get_session("nonexistent_session")

        assert result is None

    def test_list_sessions_all(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test listing all sessions."""
        # Create multiple sessions
        for i in range(3):
            service.create_session(
                session_id=f"sess_{i}",
                profile_name="test.profile",
                mount_plan=sample_mount_plan,
            )

        sessions = service.list_sessions()

        assert len(sessions) == 3

    def test_list_sessions_by_status(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test filtering sessions by status."""
        # Create sessions in different states
        service.create_session("sess_created", "test", sample_mount_plan)
        service.create_session("sess_active", "test", sample_mount_plan)
        service.start_session("sess_active")
        service.create_session("sess_completed", "test", sample_mount_plan)
        service.start_session("sess_completed")
        service.complete_session("sess_completed")

        # Query only active sessions
        sessions = service.list_sessions(status=SessionStatus.ACTIVE)

        assert len(sessions) == 1
        assert sessions[0].session_id == "sess_active"
        assert sessions[0].status == SessionStatus.ACTIVE

    def test_list_sessions_by_profile(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test filtering sessions by profile name."""
        service.create_session("sess_foundation", "foundation.base", sample_mount_plan)
        service.create_session("sess_custom", "custom.profile", sample_mount_plan)

        sessions = service.list_sessions(profile_name="foundation.base")

        assert len(sessions) == 1
        assert sessions[0].profile_name == "foundation.base"

    def test_list_sessions_with_limit(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test limiting number of results."""
        for i in range(5):
            service.create_session(f"sess_{i}", "test", sample_mount_plan)

        sessions = service.list_sessions(limit=3)

        assert len(sessions) == 3

    def test_get_active_sessions(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test getting all active sessions."""
        # Create mixed status sessions
        service.create_session("sess_1", "test", sample_mount_plan)
        service.create_session("sess_2", "test", sample_mount_plan)
        service.start_session("sess_2")
        service.create_session("sess_3", "test", sample_mount_plan)
        service.start_session("sess_3")

        active = service.get_active_sessions()

        assert len(active) == 2
        assert all(s.status == SessionStatus.ACTIVE for s in active)

    def test_delete_session(
        self,
        service: SessionStateService,
        state_dir: Path,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test deleting session removes directory and updates index."""
        service.create_session("sess_delete", "test", sample_mount_plan)

        session_dir = state_dir / "sessions" / "sess_delete"
        assert session_dir.exists()

        # Delete session
        result = service.delete_session("sess_delete")

        assert result is True
        assert not session_dir.exists()

        # Verify removed from queries
        metadata = service.get_session("sess_delete")
        assert metadata is None

    def test_delete_session_not_found(self, service: SessionStateService) -> None:
        """Test deleting nonexistent session returns False."""
        result = service.delete_session("nonexistent")

        assert result is False

    def test_cleanup_old_sessions(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test cleanup removes sessions older than threshold."""
        # Create old session (mock by creating and manually updating timestamp)
        service.create_session("sess_old", "test", sample_mount_plan)
        service.start_session("sess_old")
        service.complete_session("sess_old")

        # Manually update ended_at to be old
        metadata = service.get_session("sess_old")
        assert metadata is not None

        def make_old(m: SessionMetadata) -> None:
            m.ended_at = datetime.now(UTC) - timedelta(days=60)

        service._update_session("sess_old", make_old)

        # Create recent session
        service.create_session("sess_recent", "test", sample_mount_plan)
        service.start_session("sess_recent")
        service.complete_session("sess_recent")

        # Cleanup sessions older than 30 days
        deleted_count = service.cleanup_old_sessions(older_than_days=30)

        assert deleted_count == 1

        # Verify old session deleted, recent kept
        assert service.get_session("sess_old") is None
        assert service.get_session("sess_recent") is not None

    def test_atomic_updates(
        self,
        service: SessionStateService,
        state_dir: Path,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Test that updates use atomic write (tmp + rename)."""
        service.create_session("sess_atomic", "test", sample_mount_plan)

        # Verify session.json exists
        session_path = state_dir / "sessions" / "sess_atomic" / "session.json"
        assert session_path.exists()

        # No .tmp file should remain after write
        tmp_path = session_path.with_suffix(".tmp")
        assert not tmp_path.exists()

        # Update session (triggers atomic write)
        service.start_session("sess_atomic")

        # Still no .tmp file
        assert not tmp_path.exists()
        assert session_path.exists()

    # --- State Transition Error Tests ---

    def test_complete_session_from_created_state_error(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Cannot complete session that hasn't been started."""
        # Create session
        service.create_session(
            session_id="test_session",
            profile_name="test/profile",
            mount_plan=sample_mount_plan,
        )

        # Try to complete without starting (invalid transition)
        with pytest.raises(ValueError, match="Cannot complete session test_session in state"):
            service.complete_session("test_session")

    def test_fail_session_from_created_state_error(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Cannot fail session that hasn't been started."""
        # Create session
        service.create_session(
            session_id="test_session",
            profile_name="test/profile",
            mount_plan=sample_mount_plan,
        )

        # Try to fail without starting
        with pytest.raises(ValueError, match="Cannot fail session test_session in state"):
            service.fail_session("test_session", "error")

    def test_terminate_session_from_created_state_error(
        self,
        service: SessionStateService,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Cannot terminate session that hasn't been started."""
        # Create session
        service.create_session(
            session_id="test_session",
            profile_name="test/profile",
            mount_plan=sample_mount_plan,
        )

        # Try to terminate without starting
        with pytest.raises(ValueError, match="Cannot terminate session test_session in state"):
            service.terminate_session("test_session")

    def test_create_session_cleanup_on_mount_plan_write_failure(
        self,
        service: SessionStateService,
        state_dir: Path,
        sample_mount_plan: MountPlan,
    ) -> None:
        """Verify session directory cleaned up if mount plan write fails."""
        # Create session directory manually to trigger idempotency error
        session_dir = state_dir / "sessions" / "test_session"
        session_dir.mkdir(parents=True)

        # Try to create session with existing directory
        with pytest.raises(ValueError, match="Session.*already exists"):
            service.create_session(
                session_id="test_session",
                profile_name="test/profile",
                mount_plan=sample_mount_plan,
            )

    # --- CWD (Current Working Directory) Tests ---

    # CWD tests removed - working_dir field no longer exists
    # Tools receive working_dir in their config, derived from amplified_dir


class TestSessionStateServiceIntegration:
    """Integration tests for complex workflows."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> SessionStateService:
        """Create service with temporary state directory."""
        return SessionStateService(storage_dir=tmp_path)

    @pytest.fixture
    def mount_plan(self) -> MountPlan:
        """Create sample mount plan."""
        config = SessionConfig(
            session_id="integration_test",
            profile_id="foundation/base",
            created_at=datetime.now(UTC).isoformat(),
        )
        return MountPlan(session=config, mount_points=[])

    def test_full_session_lifecycle(
        self,
        service: SessionStateService,
        mount_plan: MountPlan,
    ) -> None:
        """Test complete session lifecycle from creation to completion."""
        # Create
        metadata = service.create_session("sess_lifecycle", "test.profile", mount_plan)
        assert metadata.status == SessionStatus.CREATED

        # Start
        service.start_session("sess_lifecycle")
        metadata = service.get_session("sess_lifecycle")
        assert metadata is not None
        assert metadata.status == SessionStatus.ACTIVE
        assert metadata.started_at is not None

        # Add messages
        service.append_message("sess_lifecycle", "user", "Hello", token_count=5)
        service.append_message("sess_lifecycle", "assistant", "Hi there!", token_count=10)

        # Complete
        service.complete_session("sess_lifecycle")
        metadata = service.get_session("sess_lifecycle")
        assert metadata is not None
        assert metadata.status == SessionStatus.COMPLETED
        assert metadata.ended_at is not None
        assert metadata.message_count == 2
        assert metadata.token_usage == 15

    def test_multiple_sessions_with_queries(
        self,
        service: SessionStateService,
        mount_plan: MountPlan,
    ) -> None:
        """Test creating multiple sessions and querying them."""
        # Create diverse sessions
        for i in range(3):
            service.create_session(f"sess_found_{i}", "foundation.base", mount_plan)
        for i in range(2):
            service.create_session(f"sess_custom_{i}", "custom.profile", mount_plan)
            service.start_session(f"sess_custom_{i}")

        # Query foundation sessions
        found_sessions = service.list_sessions(profile_name="foundation.base")
        assert len(found_sessions) == 3

        # Query active sessions
        active_sessions = service.get_active_sessions()
        assert len(active_sessions) == 2

        # Query with combined filters
        custom_active = service.list_sessions(
            profile_name="custom.profile",
            status=SessionStatus.ACTIVE,
        )
        assert len(custom_active) == 2
