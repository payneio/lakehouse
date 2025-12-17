"""Session stream manager for persistent SSE streaming.

Manages streaming infrastructure for a single session including:
- EventQueueEmitter for multi-subscriber events
- StreamingHookRegistry for hook events
- ExecutionRunner lifecycle

Note: Execution trace persistence is handled by hooks-logging (amplifier_core)
which writes to events.jsonl. Trace is aggregated on-the-fly when requested.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from amplifier_library.execution.runner import ExecutionRunner

from ..hooks import StreamingHookRegistry
from ..streaming import EventQueueEmitter  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from amplifier_library.models import Session

logger = logging.getLogger(__name__)


class SessionStreamManager:
    """Streaming infrastructure for a single session.

    Creates and coordinates:
    - EventQueueEmitter for multi-subscriber events
    - ExecutionRunner with StreamingHookRegistry
    - Connection lifecycle (subscribe/unsubscribe)

    One instance per active session with SSE connections.
    """

    def __init__(self: "SessionStreamManager", session_id: str, mount_plan: dict) -> None:
        """Initialize session stream manager.

        Args:
            session_id: Session identifier
            mount_plan: Amplifier configuration/mount plan
        """
        self.session_id = session_id
        self.mount_plan = mount_plan

        # Create streaming infrastructure
        self.emitter = EventQueueEmitter()
        # StreamingHookRegistry created in mount_hooks() to wrap the session's registry
        self.hook_registry: StreamingHookRegistry | None = None

        # ExecutionRunner (created on-demand)
        self._runner: ExecutionRunner | None = None
        self._runner_initialized = False
        self._hooks_mounted = False

        logger.info(f"Created SessionStreamManager for {session_id}")

    async def get_runner(self: "SessionStreamManager", session: "Session") -> ExecutionRunner:
        """Get or create ExecutionRunner with streaming hooks.

        Args:
            session: Session object for runner initialization

        Returns:
            ExecutionRunner configured with streaming hooks
        """
        if self._runner is None:
            # Import here to avoid circular dependency
            from amplifier_library.sessions.manager import SessionManager
            from amplifier_library.storage.paths import get_state_dir

            # Create session manager
            state_dir = get_state_dir()
            session_manager = SessionManager(state_dir)

            # Create runner
            self._runner = ExecutionRunner(
                session_manager=session_manager,
                config=self.mount_plan,
                session_id=self.session_id,
            )
            self._runner_initialized = False
            self._hooks_mounted = False
            logger.info(f"Created ExecutionRunner for session {self.session_id}")

        if not self._runner_initialized:
            # Initialize runner's session so hooks can be mounted
            logger.info(f"Initializing AmplifierSession for session {self.session_id}")
            if self._runner is not None:  # Type narrowing for pyright
                await self._runner._ensure_session()
            logger.info(f"AmplifierSession initialized for session {self.session_id}")
            self._runner_initialized = True

        # Always ensure hooks are mounted when session is available
        if self._runner is not None and self._runner._session is not None and not self._hooks_mounted:
            await self.mount_hooks(self._runner)
            self._hooks_mounted = True
            logger.info(f"Hooks mounted for session {self.session_id}")

        return self._runner

    async def mount_hooks(self: "SessionStreamManager", runner: ExecutionRunner) -> None:
        """Mount streaming hooks to runner's coordinator.

        Wraps the session's existing HookRegistry with StreamingHookRegistry
        to add SSE streaming while preserving the registry's state (including
        _defaults like session_id and parent_id set by amplifier_core).

        Args:
            runner: ExecutionRunner to mount hooks on
        """
        if runner._session is not None:
            # Wrap the existing HookRegistry with our StreamingHookRegistry
            # This preserves _defaults (session_id, parent_id) set by amplifier_core
            existing_registry = runner._session.coordinator.hooks
            self.hook_registry = StreamingHookRegistry(
                wrapped=existing_registry,
                sse_emitter=self.emitter,
                stream_events=None,  # Use defaults
            )

            # Replace with wrapped registry
            runner._session.coordinator.mount_points["hooks"] = self.hook_registry
            runner._session.coordinator.hooks = self.hook_registry

            logger.info(f"Mounted StreamingHookRegistry (wrapping existing registry) for session {self.session_id}")

    def subscribe(self: "SessionStreamManager") -> asyncio.Queue:
        """Create new SSE subscriber queue.

        Returns:
            asyncio.Queue that will receive all emitted events
        """
        return self.emitter.subscribe()

    def unsubscribe(self: "SessionStreamManager", queue: asyncio.Queue) -> None:
        """Remove SSE subscriber.

        Args:
            queue: Queue to remove
        """
        self.emitter.unsubscribe(queue)

    async def update_mount_plan(self: "SessionStreamManager", new_mount_plan: dict) -> None:
        """Update mount plan and invalidate runner.

        Args:
            new_mount_plan: New mount plan configuration
        """
        self.mount_plan = new_mount_plan
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._runner_initialized = False
        self._hooks_mounted = False
        logger.info(f"Updated mount plan for session {self.session_id}")

    async def cleanup(self: "SessionStreamManager") -> None:
        """Clean up resources when session ends."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._runner_initialized = False
        self._hooks_mounted = False
        logger.info(f"Cleaned up SessionStreamManager for {self.session_id}")
