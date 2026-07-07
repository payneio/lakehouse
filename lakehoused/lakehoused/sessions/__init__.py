"""Session management for lakehoused."""

from lakehoused.models.sessions import Session
from lakehoused.models.sessions import SessionIndex
from lakehoused.models.sessions import SessionIndexEntry
from lakehoused.models.sessions import SessionMessage
from lakehoused.models.sessions import SessionMetadata
from lakehoused.models.sessions import SessionStatus

from .manager import SessionManager

# Alias for backward compatibility with lakehoused
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
