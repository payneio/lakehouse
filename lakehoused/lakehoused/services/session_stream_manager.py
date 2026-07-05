"""Session stream manager for persistent SSE streaming.

Manages streaming infrastructure for a single session including:
- EventQueueEmitter for multi-subscriber events
- Hook handler registration for SSE streaming of hook events
- ExecutionRunner lifecycle

Note: Execution trace persistence is handled by hooks-logging (amplifier_core)
which writes to events.jsonl. Trace is aggregated on-the-fly when requested.
"""

import asyncio
import logging
from typing import TYPE_CHECKING
from typing import Any

from amplifier_core.hooks import HookResult

from lakehoused.execution.runner import ExecutionRunner

from ..hooks import DEFAULT_STREAMING_HOOKS
from ..streaming import EventQueueEmitter  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from lakehoused.models.sessions import SessionMetadata

logger = logging.getLogger(__name__)


class SessionStreamManager:
    """Streaming infrastructure for a single session.

    Creates and coordinates:
    - EventQueueEmitter for multi-subscriber events
    - ExecutionRunner with StreamingHookRegistry
    - Connection lifecycle (subscribe/unsubscribe)

    One instance per active session with SSE connections.
    """

    def __init__(self: "SessionStreamManager", session_id: str, mount_plan: dict, resolver: Any) -> None:
        """Initialize session stream manager.

        Args:
            session_id: Session identifier
            mount_plan: Amplifier configuration/mount plan
            resolver: BundleModuleResolver from Foundation (daemon-level)
        """
        self.session_id = session_id
        self.mount_plan = mount_plan
        self.resolver = resolver

        # Create streaming infrastructure
        self.emitter = EventQueueEmitter()
        # Track unregister functions from hook registration
        self._hook_unregisters: list = []

        # ExecutionRunner (created on-demand)
        self._runner: ExecutionRunner | None = None
        self._runner_initialized = False
        self._hooks_mounted = False

        # Current execution task (for cancellation support)
        self._current_execution_task: asyncio.Task | None = None

        logger.info(f"Created SessionStreamManager for {session_id}")

    async def get_runner(self: "SessionStreamManager", session: "SessionMetadata") -> ExecutionRunner:
        """Get or create ExecutionRunner with streaming hooks.

        Args:
            session: Session object for runner initialization

        Returns:
            ExecutionRunner configured with streaming hooks
        """
        if self._runner is None:
            # Import here to avoid circular dependency
            from lakehoused.sessions.manager import SessionManager
            from lakehoused.storage.paths import get_state_dir

            # Create session manager
            state_dir = get_state_dir()
            session_manager = SessionManager(state_dir)

            # Create runner with daemon-level resolver
            self._runner = ExecutionRunner(
                session_manager=session_manager,
                config=self.mount_plan,
                session_id=self.session_id,
                resolver=self.resolver,
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
        """Register a streaming hook handler on the existing registry.

        RustCoordinator.hooks is read-only, so we can't replace the hooks object.
        Instead, we register a catch-all hook handler on the existing HookRegistry
        that forwards relevant events to SSE. This is the proper amplifier-core
        pattern — hooks observe lifecycle events without needing to replace the registry.

        Args:
            runner: ExecutionRunner to mount hooks on
        """
        if runner._session is not None:
            hooks = runner._session.coordinator.hooks
            emitter = self.emitter
            stream_events = DEFAULT_STREAMING_HOOKS

            async def sse_streaming_hook(event: str, data: dict) -> HookResult:
                """Forward hook events to SSE subscribers."""
                if emitter and event in stream_events:
                    try:
                        await emitter.emit(
                            event_type=f"hook:{event}",
                            data={
                                "hook_event": event,
                                "hook_data": data,
                                "phase": "start",
                            },
                        )
                    except Exception as e:
                        logger.error(f"Failed to emit SSE event for hook {event}: {e}")
                return HookResult()

            # Register our streaming handler for each event we care about
            for event_name in stream_events:
                unregister = hooks.on(event_name, sse_streaming_hook)
                self._hook_unregisters.append(unregister)

            logger.info(f"Registered SSE streaming hook handler for session {self.session_id}")

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

    def set_execution_task(self: "SessionStreamManager", task: asyncio.Task) -> None:
        """Set the current execution task for cancellation support.

        Args:
            task: The background execution task
        """
        self._current_execution_task = task

    def clear_execution_task(self: "SessionStreamManager") -> None:
        """Clear the current execution task reference."""
        self._current_execution_task = None

    def has_active_execution(self: "SessionStreamManager") -> bool:
        """Check if there is an active execution in progress.

        Returns:
            True if an execution task is running, False otherwise
        """
        return self._current_execution_task is not None and not self._current_execution_task.done()

    def cancel_execution(self: "SessionStreamManager") -> bool:
        """Cancel the current execution if one is active.

        Returns:
            True if a task was cancelled, False if no active execution
        """
        if self.has_active_execution():
            self._current_execution_task.cancel()  # type: ignore[union-attr]
            logger.info(f"Cancelled execution for session {self.session_id}")
            return True
        return False

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
