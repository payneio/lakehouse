"""Session stream manager for persistent SSE streaming.

Manages streaming infrastructure for a single session including:
- EventQueueEmitter for multi-subscriber events
- StreamingHookRegistry for hook events
- ExecutionTraceHook for persistence
- ExecutionRunner lifecycle
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from amplifier_library.execution.runner import ExecutionRunner
from amplifier_library.storage import get_state_dir

from ..hooks import DEFAULT_STREAMING_HOOKS
from ..hooks import ExecutionTraceHook
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
        self.hook_registry = StreamingHookRegistry(
            sse_emitter=self.emitter,
            stream_events=DEFAULT_STREAMING_HOOKS,
        )

        # Create execution trace hook for persistence
        state_dir = get_state_dir()
        session_dir = state_dir / "sessions" / session_id
        self.trace_hook = ExecutionTraceHook(session_dir)

        # ExecutionRunner (created on-demand)
        self._runner: ExecutionRunner | None = None
        self._runner_initialized = False

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
            logger.info(f"Created ExecutionRunner for session {self.session_id}")

        if not self._runner_initialized:
            # Initialize runner's session so hooks can be mounted
            logger.info(f"Initializing AmplifierSession for session {self.session_id}")
            if self._runner is not None:  # Type narrowing for pyright
                await self._runner._ensure_session()
            logger.info(f"AmplifierSession initialized for session {self.session_id}")
            self._runner_initialized = True

        return self._runner

    async def mount_hooks(self: "SessionStreamManager", runner: ExecutionRunner) -> None:
        """Mount streaming hooks to runner's coordinator.

        Args:
            runner: ExecutionRunner to mount hooks on
        """
        if runner._session is not None:
            # Replace the default HookRegistry with our StreamingHookRegistry
            runner._session.coordinator.mount_points["hooks"] = self.hook_registry
            runner._session.coordinator.hooks = self.hook_registry

            # Register execution trace hook for persistence
            self.hook_registry.register("assistant_message:start", self.trace_hook.on_assistant_message_start)
            self.hook_registry.register("tool:pre", self.trace_hook.on_tool_pre)
            self.hook_registry.register("tool:post", self.trace_hook.on_tool_post)
            self.hook_registry.register("thinking:delta", self.trace_hook.on_thinking_delta)
            self.hook_registry.register("assistant_message:complete", self.trace_hook.on_assistant_message_complete)

            logger.info(f"Mounted StreamingHookRegistry and ExecutionTraceHook for session {self.session_id}")

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
        logger.info(f"Updated mount plan for session {self.session_id}")

    async def cleanup(self: "SessionStreamManager") -> None:
        """Clean up resources when session ends."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        self._runner_initialized = False
        logger.info(f"Cleaned up SessionStreamManager for {self.session_id}")
