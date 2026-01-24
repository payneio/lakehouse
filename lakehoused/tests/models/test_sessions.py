"""Unit tests for session state models."""

from datetime import UTC
from datetime import datetime

import pytest
from pydantic import ValidationError

from lakehouse_library.models.sessions import SessionIndex
from lakehouse_library.models.sessions import SessionIndexEntry
from lakehouse_library.models.sessions import SessionMessage
from lakehouse_library.models.sessions import SessionMetadata
from lakehouse_library.models.sessions import SessionQuery
from lakehouse_library.models.sessions import SessionStatus


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_all_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert SessionStatus.CREATED == "created"
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.FAILED == "failed"
        assert SessionStatus.TERMINATED == "terminated"

    def test_status_is_string_enum(self) -> None:
        """Test that SessionStatus values are strings."""
        for status in SessionStatus:
            assert isinstance(status.value, str)

    def test_status_comparison(self) -> None:
        """Test status comparison."""
        assert SessionStatus.CREATED != SessionStatus.ACTIVE
        assert SessionStatus.COMPLETED == SessionStatus.COMPLETED


class TestSessionMetadata:
    """Tests for SessionMetadata model."""

    def test_minimal_creation(self) -> None:
        """Test creating session metadata with required fields."""
        now = datetime.now()
        metadata = SessionMetadata(
            session_id="sess_123",
            status=SessionStatus.CREATED,
            created_at=now,
            bundle_name="foundation.base",
            mount_plan_path="mount_plan.json",
        )

        assert metadata.session_id == "sess_123"
        assert metadata.status == SessionStatus.CREATED
        assert metadata.created_at == now
        assert metadata.bundle_name == "foundation.base"
        assert metadata.mount_plan_path == "mount_plan.json"

        # Check defaults
        assert metadata.parent_session_id is None
        assert metadata.started_at is None
        assert metadata.ended_at is None
        assert metadata.message_count == 0
        assert metadata.agent_invocations == 0
        assert metadata.token_usage is None
        assert metadata.error_message is None
        assert metadata.error_details is None

    def test_full_creation(self) -> None:
        """Test creating session metadata with all fields."""
        created = datetime(2025, 1, 25, 10, 0, 0, tzinfo=UTC)
        started = datetime(2025, 1, 25, 10, 5, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 25, 10, 30, 0, tzinfo=UTC)

        metadata = SessionMetadata(
            session_id="sess_abc",
            parent_session_id="sess_parent",
            status=SessionStatus.COMPLETED,
            created_at=created,
            started_at=started,
            ended_at=ended,
            bundle_name="foundation.base",
            mount_plan_path="mount_plan.json",
            message_count=15,
            agent_invocations=8,
            token_usage=5000,
        )

        assert metadata.parent_session_id == "sess_parent"
        assert metadata.started_at == started
        assert metadata.ended_at == ended
        assert metadata.message_count == 15
        assert metadata.agent_invocations == 8
        assert metadata.token_usage == 5000

    def test_failed_session_with_error(self) -> None:
        """Test session metadata for failed session with error details."""
        metadata = SessionMetadata(
            session_id="sess_failed",
            status=SessionStatus.FAILED,
            created_at=datetime.now(),
            bundle_name="test.profile",
            mount_plan_path="mount_plan.json",
            error_message="Module import failed",
            error_details={"module": "provider.anthropic", "exception": "ImportError"},
        )

        assert metadata.status == SessionStatus.FAILED
        assert metadata.error_message == "Module import failed"
        assert metadata.error_details is not None
        assert metadata.error_details["module"] == "provider.anthropic"

    def test_validation_error_missing_required(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SessionMetadata()  # type: ignore - intentionally missing fields

        error = exc_info.value
        # CamelCase model uses camelCase field names in errors
        assert "sessionId" in str(error) or "session_id" in str(error)
        assert "status" in str(error)
        assert "createdAt" in str(error) or "created_at" in str(error)


class TestSessionMessage:
    """Tests for SessionMessage model."""

    def test_user_message(self) -> None:
        """Test creating user message."""
        now = datetime.now()
        message = SessionMessage(
            timestamp=now,
            role="user",
            content="Hello, how can you help me?",
        )

        assert message.timestamp == now
        assert message.role == "user"
        assert message.content == "Hello, how can you help me?"
        assert message.agent is None
        assert message.token_count is None

    def test_assistant_message(self) -> None:
        """Test creating assistant message."""
        message = SessionMessage(
            timestamp=datetime.now(),
            role="assistant",
            content="I can help you with various tasks.",
            token_count=25,
        )

        assert message.role == "assistant"
        assert message.token_count == 25

    def test_agent_message(self) -> None:
        """Test creating message from specific agent."""
        message = SessionMessage(
            timestamp=datetime.now(),
            role="assistant",
            content="Analysis complete.",
            agent="zen-architect",
            token_count=15,
        )

        assert message.role == "assistant"
        assert message.agent == "zen-architect"
        assert message.token_count == 15

    def test_system_message(self) -> None:
        """Test creating system message."""
        message = SessionMessage(
            timestamp=datetime.now(),
            role="system",
            content="Session initialized",
        )

        assert message.role == "system"


class TestSessionIndexEntry:
    """Tests for SessionIndexEntry model."""

    def test_minimal_entry(self) -> None:
        """Test creating minimal index entry."""
        now = datetime.now()
        entry = SessionIndexEntry(
            session_id="sess_123",
            status=SessionStatus.CREATED,
            bundle_name="foundation.base",
            created_at=now,
        )

        assert entry.session_id == "sess_123"
        assert entry.status == SessionStatus.CREATED
        assert entry.bundle_name == "foundation.base"
        assert entry.created_at == now
        assert entry.ended_at is None
        assert entry.message_count == 0

    def test_completed_entry(self) -> None:
        """Test index entry for completed session."""
        created = datetime(2025, 1, 25, 10, 0, 0, tzinfo=UTC)
        ended = datetime(2025, 1, 25, 10, 30, 0, tzinfo=UTC)

        entry = SessionIndexEntry(
            session_id="sess_completed",
            status=SessionStatus.COMPLETED,
            bundle_name="foundation.base",
            created_at=created,
            ended_at=ended,
            message_count=42,
        )

        assert entry.status == SessionStatus.COMPLETED
        assert entry.ended_at == ended
        assert entry.message_count == 42


class TestSessionIndex:
    """Tests for SessionIndex model."""

    def test_empty_index(self) -> None:
        """Test creating empty session index."""
        index = SessionIndex()

        assert len(index.sessions) == 0
        assert isinstance(index.last_updated, datetime)

    def test_index_with_entries(self) -> None:
        """Test creating index with session entries."""
        now = datetime.now()

        entry1 = SessionIndexEntry(
            session_id="sess_1",
            status=SessionStatus.ACTIVE,
            bundle_name="foundation.base",
            created_at=now,
        )

        entry2 = SessionIndexEntry(
            session_id="sess_2",
            status=SessionStatus.COMPLETED,
            bundle_name="foundation.base",
            created_at=now,
        )

        index = SessionIndex(
            sessions={
                "sess_1": entry1,
                "sess_2": entry2,
            },
            last_updated=now,
        )

        assert len(index.sessions) == 2
        assert "sess_1" in index.sessions
        assert "sess_2" in index.sessions
        assert index.sessions["sess_1"].status == SessionStatus.ACTIVE
        assert index.last_updated == now

    def test_index_lookup(self) -> None:
        """Test O(1) lookup in session index."""
        entry = SessionIndexEntry(
            session_id="sess_fast_lookup",
            status=SessionStatus.ACTIVE,
            bundle_name="test.profile",
            created_at=datetime.now(),
        )

        index = SessionIndex(sessions={"sess_fast_lookup": entry})

        # O(1) lookup by session_id
        assert "sess_fast_lookup" in index.sessions
        retrieved = index.sessions["sess_fast_lookup"]
        assert retrieved.session_id == "sess_fast_lookup"


class TestSessionQuery:
    """Tests for SessionQuery model."""

    def test_empty_query(self) -> None:
        """Test query with no filters (all optional)."""
        query = SessionQuery()

        assert query.status is None
        assert query.bundle_name is None
        assert query.since is None
        assert query.limit is None

    def test_status_filter(self) -> None:
        """Test query with status filter."""
        query = SessionQuery(status=SessionStatus.ACTIVE)

        assert query.status == SessionStatus.ACTIVE
        assert query.bundle_name is None

    def test_profile_filter(self) -> None:
        """Test query with profile name filter."""
        query = SessionQuery(bundle_name="foundation.base")

        assert query.bundle_name == "foundation.base"

    def test_time_filter(self) -> None:
        """Test query with time filter."""
        since = datetime(2025, 1, 20, 0, 0, 0, tzinfo=UTC)
        query = SessionQuery(since=since)

        assert query.since == since

    def test_limit_filter(self) -> None:
        """Test query with result limit."""
        query = SessionQuery(limit=10)

        assert query.limit == 10

    def test_combined_filters(self) -> None:
        """Test query with multiple filters (AND logic)."""
        since = datetime(2025, 1, 20, 0, 0, 0, tzinfo=UTC)
        query = SessionQuery(
            status=SessionStatus.COMPLETED,
            bundle_name="foundation.base",
            since=since,
            limit=5,
        )

        assert query.status == SessionStatus.COMPLETED
        assert query.bundle_name == "foundation.base"
        assert query.since == since
        assert query.limit == 5


class TestSessionModelIntegration:
    """Integration tests for session models working together."""

    def test_metadata_to_index_entry(self) -> None:
        """Test converting SessionMetadata to SessionIndexEntry (conceptually)."""
        now = datetime.now()

        # Create full metadata
        metadata = SessionMetadata(
            session_id="sess_123",
            status=SessionStatus.ACTIVE,
            created_at=now,
            bundle_name="foundation.base",
            mount_plan_path="mount_plan.json",
            message_count=10,
        )

        # Create corresponding index entry (would be done by service)
        entry = SessionIndexEntry(
            session_id=metadata.session_id,
            status=metadata.status,
            bundle_name=metadata.bundle_name,
            created_at=metadata.created_at,
            ended_at=metadata.ended_at,
            message_count=metadata.message_count,
        )

        # Verify consistency
        assert entry.session_id == metadata.session_id
        assert entry.status == metadata.status
        assert entry.message_count == metadata.message_count

    def test_query_matches_entry(self) -> None:
        """Test that SessionQuery can match SessionIndexEntry."""
        now = datetime.now()

        entry = SessionIndexEntry(
            session_id="sess_match",
            status=SessionStatus.ACTIVE,
            bundle_name="foundation.base",
            created_at=now,
        )

        # Query should match
        query1 = SessionQuery(status=SessionStatus.ACTIVE)
        assert entry.status == query1.status

        query2 = SessionQuery(bundle_name="foundation.base")
        assert entry.bundle_name == query2.bundle_name

        # Query should not match
        query3 = SessionQuery(status=SessionStatus.COMPLETED)
        assert entry.status != query3.status
