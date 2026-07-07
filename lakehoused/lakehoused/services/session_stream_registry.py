"""Session stream registry.

Manages one SessionStreamManager (EventQueueEmitter + execution-task tracking) per
active session. With the opencode backend, OpencodeRunner instances are created
per-turn by the message router (they carry no long-lived amplifier session), so
there is no separate runner registry here.
"""

import asyncio
import logging

from .session_stream_manager import SessionStreamManager

logger = logging.getLogger(__name__)


class SessionStreamRegistry:
    """Global registry of active session stream managers."""

    def __init__(self: "SessionStreamRegistry") -> None:
        self._managers: dict[str, SessionStreamManager] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self: "SessionStreamRegistry", session_id: str) -> SessionStreamManager:
        """Get existing manager or create a new one."""
        async with self._lock:
            if session_id not in self._managers:
                self._managers[session_id] = SessionStreamManager(session_id)
                logger.info(f"Created SessionStreamManager for session {session_id}")
            return self._managers[session_id]

    def get(self: "SessionStreamRegistry", session_id: str) -> SessionStreamManager | None:
        """Get an existing manager (no creation)."""
        return self._managers.get(session_id)

    async def cleanup_session(self: "SessionStreamRegistry", session_id: str) -> None:
        """Remove manager when a session ends."""
        async with self._lock:
            if session_id in self._managers:
                await self._managers[session_id].cleanup()
                del self._managers[session_id]
                logger.info(f"Cleaned up SessionStreamManager for session {session_id}")

    async def cleanup_all(self: "SessionStreamRegistry") -> None:
        """Clean up all managers (for shutdown)."""
        async with self._lock:
            for manager in self._managers.values():
                await manager.cleanup()
            self._managers.clear()
            logger.info("Cleaned up all SessionStreamManagers")


# Global registry instance
_stream_registry = SessionStreamRegistry()


def get_stream_registry() -> SessionStreamRegistry:
    """Get the global stream registry."""
    return _stream_registry
