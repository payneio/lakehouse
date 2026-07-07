"""Session stream manager for persistent SSE streaming.

Owns the EventQueueEmitter for one session and tracks the in-flight execution task
for cancellation. With the opencode backend, hook/tool/thinking/approval events are
emitted directly to this emitter by the OpencodeRunner (translated from opencode's
event stream), so there is no hook registry to mount here.
"""

import asyncio
import logging

from ..streaming import EventQueueEmitter  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)


class SessionStreamManager:
    """Streaming infrastructure for a single session.

    Holds the EventQueueEmitter (fanned out to /stream subscribers) and the current
    execution task (for cancellation). One instance per active session.
    """

    def __init__(self: "SessionStreamManager", session_id: str) -> None:
        self.session_id = session_id
        self.emitter = EventQueueEmitter()
        self._current_execution_task: asyncio.Task | None = None
        logger.info(f"Created SessionStreamManager for {session_id}")

    def subscribe(self: "SessionStreamManager") -> asyncio.Queue:
        """Create a new SSE subscriber queue."""
        return self.emitter.subscribe()

    def unsubscribe(self: "SessionStreamManager", queue: asyncio.Queue) -> None:
        """Remove an SSE subscriber."""
        self.emitter.unsubscribe(queue)

    def set_execution_task(self: "SessionStreamManager", task: asyncio.Task) -> None:
        self._current_execution_task = task

    def clear_execution_task(self: "SessionStreamManager") -> None:
        self._current_execution_task = None

    def has_active_execution(self: "SessionStreamManager") -> bool:
        return self._current_execution_task is not None and not self._current_execution_task.done()

    def cancel_execution(self: "SessionStreamManager") -> bool:
        """Cancel the current execution if one is active."""
        if self.has_active_execution():
            self._current_execution_task.cancel()  # type: ignore[union-attr]
            logger.info(f"Cancelled execution for session {self.session_id}")
            return True
        return False

    async def cleanup(self: "SessionStreamManager") -> None:
        """Clean up resources when session ends."""
        logger.info(f"Cleaned up SessionStreamManager for {self.session_id}")
