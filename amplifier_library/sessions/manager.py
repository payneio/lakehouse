"""Session state management service."""

import logging
import shutil
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from amplifier_library.models.sessions import SessionIndex
from amplifier_library.models.sessions import SessionIndexEntry
from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session lifecycle and persistence.

    Handles session state transitions, transcript management, and queries.
    Uses atomic file operations and append-only patterns for reliability.
    """

    def __init__(self, storage_dir: Path) -> None:
        """Initialize with storage directory.

        Args:
            storage_dir: Path to parent directory - will create sessions/ subdirectory
                        (e.g., .amplifierd/state for daemon, .amplifier for CLI)
        """
        self.storage_dir = Path(storage_dir) / "sessions"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.storage_dir / "index.json"

    # --- Lifecycle Management ---

    def create_session(
        self,
        session_id: str,
        profile_name: str,
        mount_plan: Any = None,
        parent_session_id: str | None = None,
        amplified_dir: str = ".",
    ) -> SessionMetadata:
        """Create new session in CREATED state.

        Args:
            session_id: Unique session identifier
            profile_name: Profile name for this session
            mount_plan: Complete mount plan to persist
            parent_session_id: Optional parent session for sub-sessions
            amplified_dir: Relative path to amplified directory (defaults to ".")

        Returns:
            SessionMetadata for created session

        Raises:
            ValueError: If session_id already exists (idempotency)

        Side Effects:
            Creates session directory with:
            - mount_plan.json (full mount plan)
            - session.json (metadata)
            - transcript.jsonl (empty)
            Updates index.json
        """
        session_dir = self.storage_dir / session_id

        # Check idempotency
        if session_dir.exists():
            raise ValueError(f"Session {session_id} already exists")

        try:
            # Create session directory
            session_dir.mkdir(parents=True)

            # Write mount_plan.json if provided
            if mount_plan is not None:
                import json

                mount_plan_path = session_dir / "mount_plan.json"
                # Handle both Pydantic models and dicts
                if hasattr(mount_plan, "model_dump"):
                    mount_plan_data = mount_plan.model_dump()
                else:
                    mount_plan_data = mount_plan
                mount_plan_path.write_text(json.dumps(mount_plan_data, indent=2))

            # Create SessionMetadata with CREATED status
            now = datetime.now(UTC)
            metadata = SessionMetadata(
                session_id=session_id,
                amplified_dir=amplified_dir,
                session_cwd=amplified_dir,  # Start CWD at amplified_dir
                profile_name=profile_name,
                status=SessionStatus.CREATED,
                created_at=now,
                started_at=None,
                ended_at=None,
                parent_session_id=parent_session_id,
                mount_plan_path="mount_plan.json",
                message_count=0,
                agent_invocations=0,
                token_usage=None,
                error_message=None,
                error_details=None,
            )

            # Write session.json atomically
            session_path = session_dir / "session.json"
            tmp_path = session_path.with_suffix(".tmp")
            tmp_path.write_text(metadata.model_dump_json(indent=2))
            tmp_path.rename(session_path)

            # Create empty transcript.jsonl
            transcript_path = session_dir / "transcript.jsonl"
            transcript_path.touch()

            # Update index
            self._update_index(metadata)

            logger.info(f"Created session {session_id} with profile {profile_name}")
            return metadata

        except Exception as e:
            # Cleanup partial session on any failure
            if session_dir.exists():
                shutil.rmtree(session_dir)
            logger.error(f"Failed to create session {session_id}: {e}")
            raise

    def start_session(self, session_id: str) -> None:
        """Transition CREATED → ACTIVE."""

        def update(metadata: SessionMetadata) -> None:
            if metadata.status != SessionStatus.CREATED:
                raise ValueError(f"Cannot start session {session_id} in state {metadata.status}")
            metadata.status = SessionStatus.ACTIVE
            metadata.started_at = datetime.now(UTC)

        self._update_session(session_id, update)
        logger.info(f"Started session {session_id}")

    def complete_session(self, session_id: str) -> None:
        """Transition ACTIVE → COMPLETED."""

        def update(metadata: SessionMetadata) -> None:
            if metadata.status != SessionStatus.ACTIVE:
                raise ValueError(f"Cannot complete session {session_id} in state {metadata.status}")
            metadata.status = SessionStatus.COMPLETED
            metadata.ended_at = datetime.now(UTC)

        self._update_session(session_id, update)
        logger.info(f"Completed session {session_id}")

    def fail_session(
        self,
        session_id: str,
        error_message: str,
        error_details: dict | None = None,
    ) -> None:
        """Transition ACTIVE → FAILED."""

        def update(metadata: SessionMetadata) -> None:
            if metadata.status != SessionStatus.ACTIVE:
                raise ValueError(f"Cannot fail session {session_id} in state {metadata.status}")
            metadata.status = SessionStatus.FAILED
            metadata.ended_at = datetime.now(UTC)
            metadata.error_message = error_message
            metadata.error_details = error_details

        self._update_session(session_id, update)
        logger.warning(f"Failed session {session_id}: {error_message}")

    def terminate_session(self, session_id: str) -> None:
        """Transition ACTIVE → TERMINATED."""

        def update(metadata: SessionMetadata) -> None:
            if metadata.status != SessionStatus.ACTIVE:
                raise ValueError(f"Cannot terminate session {session_id} in state {metadata.status}")
            metadata.status = SessionStatus.TERMINATED
            metadata.ended_at = datetime.now(UTC)

        self._update_session(session_id, update)
        logger.info(f"Terminated session {session_id}")

    # --- Transcript Management ---

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        agent: str | None = None,
        token_count: int | None = None,
    ) -> None:
        """Append message to transcript (efficient append-only).

        Args:
            session_id: Session identifier
            role: Message role ("user" | "assistant" | "system")
            content: Message content
            agent: Optional agent identifier
            token_count: Optional token count

        Side Effects:
            Appends line to transcript.jsonl
            Updates message_count in session.json
            Updates token_usage if token_count provided
        """
        transcript_path = self.storage_dir / session_id / "transcript.jsonl"

        # Ensure session directory exists
        transcript_path.parent.mkdir(parents=True, exist_ok=True)

        # Create SessionMessage
        message = SessionMessage(
            timestamp=datetime.now(UTC),
            role=role,
            content=content,
            agent=agent,
            token_count=token_count,
        )

        # Append to transcript.jsonl
        with open(transcript_path, "a") as f:
            f.write(message.model_dump_json() + "\n")

        # Update metadata counts
        def update(metadata: SessionMetadata) -> None:
            metadata.message_count += 1
            if token_count:
                metadata.token_usage = (metadata.token_usage or 0) + token_count

        self._update_session(session_id, update)

    def get_transcript(self, session_id: str, limit: int | None = None) -> list[SessionMessage]:
        """Read transcript (optionally limited to last N messages)."""
        transcript_path = self.storage_dir / session_id / "transcript.jsonl"

        if not transcript_path.exists():
            return []

        # Read all lines
        lines = transcript_path.read_text().strip().split("\n")
        if not lines or lines == [""]:
            return []

        # Parse each line as SessionMessage
        messages = [SessionMessage.model_validate_json(line) for line in lines if line]

        # Return last N if limit provided
        if limit is not None:
            return messages[-limit:]
        return messages

    # --- Queries ---

    def get_session(self, session_id: str) -> SessionMetadata | None:
        """Get session metadata by ID."""
        session_path = self.storage_dir / session_id / "session.json"

        if not session_path.exists():
            return None

        return SessionMetadata.model_validate_json(session_path.read_text())

    def list_sessions(
        self,
        status: SessionStatus | None = None,
        profile_name: str | None = None,
        amplified_dir: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[SessionMetadata]:
        """Query sessions with filters.

        Uses index for fast filtering, then loads full metadata.

        Args:
            status: Optional filter by session status
            profile_name: Optional filter by profile name
            amplified_dir: Optional filter by amplified directory path
            since: Optional filter by creation time
            limit: Optional maximum number of results

        Returns:
            List of session metadata matching filters, sorted by creation time descending
        """
        # Load index
        index = self._load_index()

        # Apply filters to index entries
        filtered_ids: list[str] = []
        for entry in index.sessions.values():
            if status is not None and entry.status != status:
                continue
            if profile_name is not None and entry.profile_name != profile_name:
                continue
            if amplified_dir is not None and entry.amplified_dir != amplified_dir:
                continue
            if since is not None and entry.created_at < since:
                continue
            filtered_ids.append(entry.session_id)

        # Load full metadata for matches
        results: list[SessionMetadata] = []
        for session_id in filtered_ids:
            metadata = self.get_session(session_id)
            if metadata:
                results.append(metadata)

        # Sort by created_at descending (most recent first)
        results.sort(key=lambda m: m.created_at, reverse=True)

        # Apply limit if provided
        if limit is not None:
            return results[:limit]
        return results

    def get_active_sessions(self) -> list[SessionMetadata]:
        """Get all ACTIVE sessions."""
        return self.list_sessions(status=SessionStatus.ACTIVE)

    def get_session_cwd(self, session_id: str) -> Path:
        """Get the working directory for a session.

        Args:
            session_id: Session identifier

        Returns:
            Absolute path to the session's current working directory

        Raises:
            ValueError: If session not found

        Example:
            >>> cwd = service.get_session_cwd("session-123")
            >>> print(cwd)
            /data/projects/my-project
        """
        metadata = self.get_session(session_id)
        if metadata is None:
            raise ValueError(f"Cannot get CWD: session not found: {session_id}")
        return metadata.cwd

    # --- Management ---

    def delete_session(self, session_id: str) -> bool:
        """Delete session directory and remove from index."""
        session_dir = self.storage_dir / session_id

        if not session_dir.exists():
            return False

        try:
            # Remove directory
            shutil.rmtree(session_dir)

            # Update index
            index = self._load_index()
            if session_id in index.sessions:
                del index.sessions[session_id]
                self._save_index(index)

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def cleanup_old_sessions(
        self,
        older_than_days: int = 30,
        keep_statuses: set[SessionStatus] | None = None,
    ) -> int:
        """Remove sessions older than threshold (except protected statuses).

        Args:
            older_than_days: Age threshold in days
            keep_statuses: Statuses to preserve (default: {ACTIVE})

        Returns:
            Number of sessions removed
        """
        # Default keep_statuses to {ACTIVE}
        if keep_statuses is None:
            keep_statuses = {SessionStatus.ACTIVE}

        # Calculate cutoff datetime
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)

        # Iterate index
        index = self._load_index()
        to_delete: list[str] = []

        for entry in index.sessions.values():
            # Skip protected statuses
            if entry.status in keep_statuses:
                continue

            # Check age (use ended_at if available, else created_at)
            check_time = entry.ended_at if entry.ended_at else entry.created_at
            if check_time < cutoff:
                to_delete.append(entry.session_id)

        # Delete old sessions
        deleted_count = 0
        for session_id in to_delete:
            if self.delete_session(session_id):
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} sessions older than {older_than_days} days")

        return deleted_count

    # --- Helpers ---

    def _update_session(self, session_id: str, update_fn: Callable[[SessionMetadata], None]) -> None:
        """Atomically update session metadata.

        Uses tmp + rename pattern for atomic updates.
        Updates index after successful write.
        """
        session_path = self.storage_dir / session_id / "session.json"

        if not session_path.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        # Read
        metadata = SessionMetadata.model_validate_json(session_path.read_text())

        # Modify
        update_fn(metadata)

        # Write atomically
        tmp_path = session_path.with_suffix(".tmp")
        tmp_path.write_text(metadata.model_dump_json(indent=2))
        tmp_path.rename(session_path)

        # Update index
        self._update_index(metadata)

    def _load_index(self) -> SessionIndex:
        """Load session index from disk."""
        if not self.index_path.exists():
            return SessionIndex(sessions={}, last_updated=datetime.now(UTC))

        return SessionIndex.model_validate_json(self.index_path.read_text())

    def _save_index(self, index: SessionIndex) -> None:
        """Save session index to disk atomically."""
        # Update last_updated
        index.last_updated = datetime.now(UTC)

        # Write to tmp file
        tmp_path = self.index_path.with_suffix(".tmp")
        tmp_path.write_text(index.model_dump_json(indent=2))

        # Rename to index.json (atomic)
        tmp_path.rename(self.index_path)

    def _update_index(self, metadata: SessionMetadata) -> None:
        """Update index entry for session."""
        # Load index
        index = self._load_index()

        # Create SessionIndexEntry from metadata
        entry = SessionIndexEntry(
            session_id=metadata.session_id,
            amplified_dir=metadata.amplified_dir,
            profile_name=metadata.profile_name,
            status=metadata.status,
            created_at=metadata.created_at,
            ended_at=metadata.ended_at,
            message_count=metadata.message_count,
        )

        # Update sessions dict
        index.sessions[metadata.session_id] = entry

        # Save index
        self._save_index(index)
