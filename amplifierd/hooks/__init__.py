"""Hook system extensions for amplifierd.

Provides StreamingHookRegistry that bridges amplifier-core hooks
to frontend via SSE events.
"""

import logging
from typing import Any
from typing import Optional

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
}


class StreamingHookRegistry(HookRegistry):
    """Enhanced HookRegistry that emits SSE events for configured hooks.

    Wraps standard HookRegistry to add SSE streaming capability while
    preserving all existing hook behavior. When hooks fire, they are
    optionally streamed to frontend subscribers via SSE.

    Example:
        sse_emitter = EventQueueEmitter()
        hooks = StreamingHookRegistry(
            sse_emitter=sse_emitter,
            stream_events={"tool:pre", "tool:post"}
        )

        result = await hooks.emit("tool:pre", {"tool_name": "read"})
    """

    def __init__(
        self: "StreamingHookRegistry",
        sse_emitter: Any | None = None,
        stream_events: set[str] | None = None,
    ) -> None:
        """Initialize streaming hook registry.

        Args:
            sse_emitter: Emitter implementing emit(event_type, data) for SSE
            stream_events: Set of hook event names to stream (defaults to DEFAULT_STREAMING_HOOKS)
        """
        super().__init__()
        self.sse_emitter = sse_emitter
        self.stream_events = stream_events or DEFAULT_STREAMING_HOOKS

    async def emit(self: "StreamingHookRegistry", event: str, data: dict[str, Any]) -> HookResult:
        """Emit hook event with optional SSE streaming.

        Args:
            event: Hook event name (e.g., "tool:pre")
            data: Event payload

        Returns:
            HookResult from registered handlers
        """
        if self.sse_emitter and event in self.stream_events:
            try:
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

        result = await super().emit(event, data)

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
