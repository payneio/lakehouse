"""Session management for amplifier library."""

from amplifier_library.models.sessions import Session
from amplifier_library.models.sessions import SessionIndex
from amplifier_library.models.sessions import SessionIndexEntry
from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus

from .manager import SessionManager

# Alias for backward compatibility with amplifierd
SessionStateService = SessionManager

__all__ = [
    "SessionManager",
    "SessionStateService",
    "Session",
    "SessionMetadata",
    "SessionMessage",
    "SessionStatus",
    "SessionIndex",
    "SessionIndexEntry",
]
