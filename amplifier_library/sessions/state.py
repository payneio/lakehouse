"""Compatibility layer for session state operations.

This module provides backward-compatible functions that wrap SessionStateService.
"""

from amplifier_library.models.sessions import Session
from amplifier_library.models.sessions import SessionMessage
from amplifier_library.storage.paths import get_state_dir

from .manager import SessionManager as SessionStateService


def _get_service() -> SessionStateService:
    """Get SessionStateService instance.

    Returns:
        SessionStateService configured with state directory
    """
    return SessionStateService(storage_dir=get_state_dir())


def add_message(
    session: Session,
    role: str,
    content: str,
    agent: str | None = None,
    token_count: int | None = None,
) -> SessionMessage:
    """Add a message to session transcript.

    Args:
        session: Session object
        role: Message role ("user" | "assistant" | "system")
        content: Message content
        agent: Optional agent identifier
        token_count: Optional token count

    Returns:
        Created SessionMessage

    Side Effects:
        Appends message to transcript.jsonl
        Updates message_count in session.json
    """
    service = _get_service()
    service.append_message(
        session_id=session.session_id,
        role=role,
        content=content,
        agent=agent,
        token_count=token_count,
    )

    # Return a SessionMessage for backward compatibility
    from datetime import UTC
    from datetime import datetime

    return SessionMessage(
        timestamp=datetime.now(UTC),
        role=role,
        content=content,
        agent=agent,
        token_count=token_count,
    )


def get_transcript(session_id: str) -> list[SessionMessage]:
    """Get session transcript.

    Args:
        session_id: Session identifier

    Returns:
        List of SessionMessage objects

    Raises:
        FileNotFoundError: If session doesn't exist
    """
    service = _get_service()
    return service.get_transcript(session_id)


def update_context(session: Session, updates: dict) -> None:
    """Update session context (deprecated - contexts removed from new model).

    Args:
        session: Session object
        updates: Context updates (ignored in new model)

    Note:
        This function is a no-op for backward compatibility.
        The new SessionMetadata model doesn't have a context field.
    """
    # No-op: contexts don't exist in new model
    return  # Explicit no-op for backward compatibility
