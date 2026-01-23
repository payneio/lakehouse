"""Session state models for lifecycle management."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from pydantic import Field
from pydantic import computed_field
from pydantic import model_validator

from amplifier_library.config.loader import load_config
from amplifier_library.models.base import CamelCaseModel

if TYPE_CHECKING:
    from pathlib import Path


class SessionStatus(str, Enum):
    """Session lifecycle status.

    State transitions:
    - CREATED: (Legacy) Mount plan generated, session not yet started
                Kept for backwards compatibility with old sessions
    - ACTIVE: Session running, messages being exchanged
              New sessions start in this state (as of v0.2.0)
    - COMPLETED: Session finished successfully (from ACTIVE)
    - FAILED: Error occurred during execution (from ACTIVE)
    - TERMINATED: Session killed by user (from ACTIVE)

    Valid transitions:
    - CREATED → ACTIVE (legacy only, via start_session)
    - ACTIVE → COMPLETED (via complete_session)
    - ACTIVE → FAILED (via fail_session)
    - ACTIVE → TERMINATED (via terminate_session)
    """

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class SessionMetadata(CamelCaseModel):
    """Session metadata and state.

    Tracks the lifecycle and metrics of a session. Updated as session
    progresses through states. Stored in state/sessions/{session_id}/session.json.
    """

    session_id: str = Field(description="Unique session identifier")
    name: str | None = Field(default=None, description="User-defined session name (optional, max 200 chars)")
    parent_session_id: str | None = Field(default=None, description="Parent session ID for sub-sessions")
    amplified_dir: str = Field(
        default=".", description="Relative path to amplified directory (immutable anchor for .amplified/ config)"
    )
    status: SessionStatus = Field(description="Current session status")
    created_at: datetime = Field(description="Session creation timestamp")
    started_at: datetime | None = Field(default=None, description="Session start timestamp (ACTIVE)")
    ended_at: datetime | None = Field(default=None, description="Session end timestamp (final state)")
    bundle_name: str = Field(default="", description="Bundle used for this session")
    # Backward compatibility: old sessions have profile_name instead of bundle_name
    profile_name: str | None = Field(default=None, exclude=True, description="Legacy field - use bundle_name")
    mount_plan_path: str = Field(description="Relative path to mount_plan.json")
    message_count: int = Field(default=0, description="Number of messages exchanged")
    agent_invocations: int = Field(default=0, description="Number of agent invocations")
    token_usage: int | None = Field(default=None, description="Total tokens consumed")
    error_message: str | None = Field(default=None, description="Error message if status is FAILED")
    error_details: dict[str, Any] | None = Field(default=None, description="Additional error context")
    is_unread: bool = Field(default=False, description="Whether session has unread content")
    last_read_at: datetime | None = Field(default=None, description="When session was last marked as read")

    @model_validator(mode="before")
    @classmethod
    def migrate_profile_name(cls, data: Any) -> Any:
        """Migrate legacy profile_name to bundle_name for backward compatibility."""
        if isinstance(data, dict):
            # If bundle_name is missing or empty but profile_name exists, use profile_name
            if not data.get("bundle_name") and data.get("profile_name"):
                data["bundle_name"] = data["profile_name"]
        return data


class SessionMessage(CamelCaseModel):
    """Single message in session transcript.

    Stored in JSONL format (one per line) in state/sessions/{session_id}/transcript.jsonl.
    Each line is a complete JSON object representing one message.
    """

    timestamp: datetime = Field(description="Message timestamp")
    role: str = Field(description="Message role: user, assistant, or system")
    content: str = Field(description="Message content")
    agent: str | None = Field(default=None, description="Agent name if message from agent")
    token_count: int | None = Field(default=None, description="Token count for this message")


class SessionIndexEntry(CamelCaseModel):
    """Lightweight entry in session index.

    Used for fast lookups without loading full session metadata.
    Enables queries like "list all active sessions" or "find sessions by bundle".
    """

    session_id: str = Field(description="Session identifier")
    amplified_dir: str = Field(default=".", description="Relative path to amplified directory")
    status: SessionStatus = Field(description="Current session status")
    bundle_name: str = Field(default="", description="Bundle used for this session")
    # Backward compatibility: old index entries may have profile_name
    profile_name: str | None = Field(default=None, exclude=True, description="Legacy field - use bundle_name")
    created_at: datetime = Field(description="Session creation timestamp")
    ended_at: datetime | None = Field(default=None, description="Session end timestamp")
    message_count: int = Field(default=0, description="Number of messages exchanged")

    @model_validator(mode="before")
    @classmethod
    def migrate_profile_name(cls, data: Any) -> Any:
        """Migrate legacy profile_name to bundle_name for backward compatibility."""
        if isinstance(data, dict):
            if not data.get("bundle_name") and data.get("profile_name"):
                data["bundle_name"] = data["profile_name"]
        return data


class SessionIndex(CamelCaseModel):
    """Index of all sessions for fast queries.

    Stored in state/sessions/index.json and rebuilt on session changes.
    Provides O(1) lookup by session_id and enables fast filtering by status/profile.
    """

    sessions: dict[str, SessionIndexEntry] = Field(default_factory=dict, description="Map of session_id to index entry")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last index update timestamp")


class SessionQuery(CamelCaseModel):
    """Query parameters for listing sessions.

    Used by API endpoints to filter sessions. All parameters are optional
    and combine as AND filters (all must match).
    """

    status: SessionStatus | None = Field(default=None, description="Filter by session status")
    bundle_name: str | None = Field(default=None, description="Filter by bundle name")
    since: datetime | None = Field(default=None, description="Filter sessions created after this time")
    limit: int | None = Field(default=None, description="Maximum number of results to return")


# Alias for backward compatibility
Session = SessionMetadata
