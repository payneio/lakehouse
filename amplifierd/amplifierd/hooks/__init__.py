"""Hook system extensions for amplifierd.

Provides StreamingHookRegistry that wraps amplifier-core hooks
to bridge events to frontend via SSE.
"""

import logging
from typing import Any

from amplifier_core.hooks import HookRegistry
from amplifier_core.hooks import HookResult

logger = logging.getLogger(__name__)

DEFAULT_STREAMING_HOOKS = {
    "tool:pre",
    "tool:post",
    "content_block:start",
    "content_block:end",
    "thinking:delta",
    "approval:required",
    "approval:granted",
    "approval:denied",
    "assistant_message:start",
    "assistant_message:complete",
}

__all__ = ["StreamingHookRegistry", "DEFAULT_STREAMING_HOOKS"]


class StreamingHookRegistry(HookRegistry):
    """Decorator that wraps an existing HookRegistry to add SSE streaming.

    Uses the decorator pattern to preserve the wrapped registry's state
    (including _defaults like session_id, parent_id) while adding streaming
    capability. All method calls delegate to the wrapped registry.

    NOTE: Inherits from HookRegistry for isinstance() compatibility but
    does NOT call super().__init__() - we delegate to _wrapped instead.

    Example:
        # Wrap an existing registry (preserves its _defaults)
        original_hooks = session.coordinator.hooks
        streaming_hooks = StreamingHookRegistry(
            wrapped=original_hooks,
            sse_emitter=sse_emitter,
            stream_events={"tool:pre", "tool:post"}
        )
        session.coordinator.hooks = streaming_hooks
    """

    def __init__(
        self: "StreamingHookRegistry",
        wrapped: HookRegistry | None = None,
        sse_emitter: Any | None = None,
        stream_events: set[str] | None = None,
    ) -> None:
        """Initialize streaming hook registry wrapper.

        Args:
            wrapped: Existing HookRegistry to wrap (preserves its _defaults).
                     If None, creates a new HookRegistry (for backwards compat).
            sse_emitter: Emitter implementing emit(event_type, data) for SSE
            stream_events: Set of hook event names to stream (defaults to DEFAULT_STREAMING_HOOKS)
        """
        # NOTE: Intentionally NOT calling super().__init__()
        # We delegate to _wrapped instead of managing our own state
        if wrapped is None:
            # Backwards compatibility: create fresh registry if none provided
            self._wrapped = HookRegistry()
        else:
            self._wrapped = wrapped
        self.sse_emitter = sse_emitter
        self.stream_events = stream_events or DEFAULT_STREAMING_HOOKS

    async def emit(self: "StreamingHookRegistry", event: str, data: dict[str, Any]) -> HookResult:
        """Emit hook event with optional SSE streaming.

        Streams to frontend before and after delegating to wrapped registry.

        Args:
            event: Hook event name (e.g., "tool:pre")
            data: Event payload

        Returns:
            HookResult from registered handlers
        """
        logger.debug(
            f"[StreamingHookRegistry] Emitting event: {event}, "
            f"has_emitter: {self.sse_emitter is not None}, "
            f"in_stream_events: {event in self.stream_events}"
        )

        # Stream "start" to frontend
        if self.sse_emitter and event in self.stream_events:
            try:
                logger.debug(f"[StreamingHookRegistry] Sending SSE event: hook:{event}")
                await self.sse_emitter.emit(
                    event_type=f"hook:{event}",
                    data={
                        "hook_event": event,
                        "hook_data": data,
                        "phase": "start",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to emit SSE event for hook {event}: {e}")

        # Delegate to wrapped registry (preserves _defaults like session_id)
        result = await self._wrapped.emit(event, data)

        # Stream "result" to frontend
        if self.sse_emitter and event in self.stream_events:
            try:
                await self.sse_emitter.emit(
                    event_type=f"hook:{event}:result",
                    data={
                        "hook_event": event,
                        "action": result.action,
                        "reason": result.reason,
                        "phase": "end",
                    },
                )
            except Exception as e:
                logger.error(f"Failed to emit SSE result event for hook {event}: {e}")

        return result

    # Delegate all other methods to wrapped registry
    def register(self, *args, **kwargs):
        """Delegate to wrapped registry."""
        return self._wrapped.register(*args, **kwargs)

    def on(self, *args, **kwargs):
        """Delegate to wrapped registry."""
        return self._wrapped.on(*args, **kwargs)

    def set_default_fields(self, **defaults):
        """Delegate to wrapped registry."""
        return self._wrapped.set_default_fields(**defaults)

    async def emit_and_collect(self, *args, **kwargs):
        """Delegate to wrapped registry."""
        return await self._wrapped.emit_and_collect(*args, **kwargs)

    def list_handlers(self, *args, **kwargs):
        """Delegate to wrapped registry."""
        return self._wrapped.list_handlers(*args, **kwargs)

    @property
    def _handlers(self):
        """Expose wrapped registry's handlers for compatibility."""
        return self._wrapped._handlers

    @property
    def _defaults(self):
        """Expose wrapped registry's defaults for compatibility."""
        return getattr(self._wrapped, "_defaults", {})
