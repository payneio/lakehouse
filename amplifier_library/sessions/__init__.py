"""Session management for amplifier library."""

from amplifier_library.models.sessions import Session
from amplifier_library.models.sessions import SessionIndex
from amplifier_library.models.sessions import SessionIndexEntry
from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus

from .manager import SessionManager
from .spawner import AgentNotFoundError
from .spawner import ExecutionError
from .spawner import SessionNotFoundError
from .spawner import resume_spawned_agent
from .spawner import spawn_agent

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
    "spawn_agent",
    "resume_spawned_agent",
    "AgentNotFoundError",
    "ExecutionError",
    "SessionNotFoundError",
]
