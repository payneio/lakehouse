"""Session stream and execution runner registries.

Provides:
- SessionStreamRegistry: Manages SessionStreamManager instances (for SSE streaming)
- ExecutionRunnerRegistry: Manages ExecutionRunner instances (for profile switching)
"""

import asyncio
import logging
from datetime import datetime
from datetime import timedelta
from typing import Any

from amplifier_library.execution.runner import ExecutionRunner

from .session_stream_manager import SessionStreamManager

logger = logging.getLogger(__name__)


class SessionStreamRegistry:
    """Global registry of active session stream managers.

    Singleton managing SessionStreamManager instances.
    One manager per session with active SSE connections.
    """

    def __init__(self: "SessionStreamRegistry") -> None:
        """Initialize registry."""
        self._managers: dict[str, SessionStreamManager] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self: "SessionStreamRegistry",
        session_id: str,
        mount_plan: dict,
    ) -> SessionStreamManager:
        """Get existing manager or create new one.

        Args:
            session_id: Session identifier
            mount_plan: Amplifier configuration/mount plan

        Returns:
            SessionStreamManager for the session
        """
        async with self._lock:
            if session_id not in self._managers:
                self._managers[session_id] = SessionStreamManager(session_id, mount_plan)
                logger.info(f"Created SessionStreamManager for session {session_id}")
            return self._managers[session_id]

    async def cleanup_session(self: "SessionStreamRegistry", session_id: str) -> None:
        """Remove manager when session ends.

        Args:
            session_id: Session identifier
        """
        async with self._lock:
            if session_id in self._managers:
                manager = self._managers[session_id]
                await manager.cleanup()
                del self._managers[session_id]
                logger.info(f"Cleaned up SessionStreamManager for session {session_id}")

    def get(self: "SessionStreamRegistry", session_id: str) -> SessionStreamManager | None:
        """Get existing manager (no creation).

        Args:
            session_id: Session identifier

        Returns:
            SessionStreamManager if exists, None otherwise
        """
        return self._managers.get(session_id)

    async def cleanup_all(self: "SessionStreamRegistry") -> None:
        """Clean up all managers (for shutdown)."""
        async with self._lock:
            for session_id, manager in list(self._managers.items()):
                await manager.cleanup()
                logger.info(f"Cleaned up SessionStreamManager for session {session_id}")
            self._managers.clear()
            logger.info("Cleaned up all SessionStreamManagers")


class ExecutionRunnerRegistry:
    """Registry for tracking active ExecutionRunner instances.

    Provides get-or-create pattern, profile change coordination,
    and idle session cleanup.
    """

    def __init__(self: "ExecutionRunnerRegistry") -> None:
        """Initialize registry."""
        self._runners: dict[str, ExecutionRunner] = {}
        self._last_used: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(
        self: "ExecutionRunnerRegistry",
        session_id: str,
        mount_plan: dict[str, Any],
    ) -> ExecutionRunner:
        """Get existing ExecutionRunner or create new one.

        Args:
            session_id: Session identifier
            mount_plan: Mount plan configuration

        Returns:
            ExecutionRunner instance
        """
        async with self._lock:
            if session_id not in self._runners:
                self._runners[session_id] = ExecutionRunner(config=mount_plan, session_id=session_id)
                logger.info(f"Created new ExecutionRunner for session {session_id}")

            self._last_used[session_id] = datetime.now()
            return self._runners[session_id]

    async def change_profile(
        self: "ExecutionRunnerRegistry",
        session_id: str,
        new_mount_plan: dict[str, Any],
    ) -> None:
        """Change profile for an active session.

        Args:
            session_id: Session identifier
            new_mount_plan: New mount plan configuration

        Raises:
            ValueError: If no active runner for session
        """
        async with self._lock:
            if session_id not in self._runners:
                raise ValueError(f"No active ExecutionRunner for session {session_id}")

            runner = self._runners[session_id]

        # Release lock before calling change_profile (it has its own lock)
        await runner.change_profile(new_mount_plan)

        # Update last_used
        async with self._lock:
            self._last_used[session_id] = datetime.now()

    async def remove(self: "ExecutionRunnerRegistry", session_id: str) -> None:
        """Remove and cleanup runner for session.

        Args:
            session_id: Session identifier
        """
        async with self._lock:
            runner = self._runners.pop(session_id, None)
            self._last_used.pop(session_id, None)

            if runner:
                await runner.cleanup()
                logger.info(f"Removed ExecutionRunner for session {session_id}")

    async def cleanup_idle(
        self: "ExecutionRunnerRegistry",
        idle_timeout: timedelta = timedelta(hours=1),
    ) -> int:
        """Clean up runners idle longer than timeout.

        Args:
            idle_timeout: Maximum idle time before cleanup

        Returns:
            Number of runners cleaned up
        """
        now = datetime.now()
        to_remove = []

        async with self._lock:
            for sid, last_used in self._last_used.items():
                if now - last_used > idle_timeout:
                    to_remove.append(sid)

        # Remove outside lock to avoid deadlock
        for sid in to_remove:
            await self.remove(sid)

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} idle ExecutionRunners")

        return len(to_remove)

    def get_active_count(self: "ExecutionRunnerRegistry") -> int:
        """Get count of active runners."""
        return len(self._runners)


# Global registry instances
_stream_registry = SessionStreamRegistry()
_runner_registry = ExecutionRunnerRegistry()


def get_stream_registry() -> SessionStreamRegistry:
    """Get global stream registry.

    Returns:
        Global SessionStreamRegistry singleton
    """
    return _stream_registry


async def get_or_create_runner(session_id: str, mount_plan: dict[str, Any]) -> ExecutionRunner:
    """Get or create ExecutionRunner for session."""
    return await _runner_registry.get_or_create(session_id, mount_plan)


async def change_session_profile(session_id: str, new_mount_plan: dict[str, Any]) -> None:
    """Change profile for active session."""
    await _runner_registry.change_profile(session_id, new_mount_plan)


async def remove_runner(session_id: str) -> None:
    """Remove runner for session."""
    await _runner_registry.remove(session_id)


async def cleanup_idle_runners(idle_timeout: timedelta = timedelta(hours=1)) -> int:
    """Cleanup idle runners."""
    return await _runner_registry.cleanup_idle(idle_timeout)


def get_active_runner_count() -> int:
    """Get count of active runners."""
    return _runner_registry.get_active_count()
