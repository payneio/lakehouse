"""Session management for amplifier library."""

from lakehouse_library.models.sessions import Session
from lakehouse_library.models.sessions import SessionIndex
from lakehouse_library.models.sessions import SessionIndexEntry
from lakehouse_library.models.sessions import SessionMessage
from lakehouse_library.models.sessions import SessionMetadata
from lakehouse_library.models.sessions import SessionStatus

from .manager import SessionManager
from .spawner import AgentNotFoundError
from .spawner import ExecutionError
from .spawner import SessionNotFoundError
from .spawner import resume_spawned_agent
from .spawner import spawn_agent

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
    "spawn_agent",
    "resume_spawned_agent",
    "AgentNotFoundError",
    "ExecutionError",
    "SessionNotFoundError",
]
