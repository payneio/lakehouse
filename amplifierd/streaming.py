"""SSE streaming utilities for amplifierd.

Provides utilities for Server-Sent Events (SSE) streaming.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


async def sse_event_stream(
    generator: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """Convert async generator to SSE event stream.

    Args:
        generator: Async generator yielding event dictionaries

    Yields:
        SSE formatted event strings

    Example:
        >>> async def events():
        ...     yield {"event": "message", "data": {"content": "Hello"}}
        ...     yield {"event": "done", "data": {}}
        >>> async for event in sse_event_stream(events()):
        ...     print(event)
    """
    try:
        async for event_data in generator:
            event_type = event_data.get("event", "message")
            data = event_data.get("data", {})

            # Format as SSE
            yield format_sse_event(event_type, data)

    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
        yield format_sse_event("error", {"error": str(e)})


def format_sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event.

    Args:
        event_type: Event type (e.g., 'message', 'done', 'error')
        data: Event data dictionary

    Returns:
        SSE formatted string

    Example:
        >>> event = format_sse_event("message", {"content": "Hello"})
        >>> assert "event: message" in event
        >>> assert "data:" in event
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {json_data}\n\n"


async def wrap_execution_stream(
    token_stream: AsyncIterator[str],
) -> AsyncIterator[dict[str, Any]]:
    """Wrap token stream into event stream.

    Args:
        token_stream: AsyncIterator yielding response tokens

    Yields:
        Event dictionaries for SSE streaming
    """
    try:
        # Stream tokens as they arrive
        async for token in token_stream:
            yield {"event": "message", "data": {"type": "content", "content": token}}

        # Yield completion event
        yield {"event": "done", "data": {"type": "done"}}

    except Exception as e:
        logger.error(f"Execution error: {e}")
        yield {"event": "error", "data": {"type": "error", "error": str(e)}}


class EventQueueEmitter:
    """SSE emitter that queues events for async consumption.

    Allows multiple subscribers to receive events emitted during execution.
    Each subscriber gets their own queue to prevent blocking.
    """

    def __init__(self: "EventQueueEmitter") -> None:
        self.queues: list[asyncio.Queue[dict[str, Any]]] = []
        self._lock = asyncio.Lock()

    def subscribe(self: "EventQueueEmitter") -> asyncio.Queue[dict[str, Any]]:
        """Create new subscriber queue.

        Returns:
            asyncio.Queue that will receive all emitted events
        """
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.queues.append(queue)
        return queue

    async def emit(self: "EventQueueEmitter", event_type: str, data: dict[str, Any]) -> None:
        """Emit event to all subscriber queues.

        Args:
            event_type: Event type identifier (e.g., "hook:tool:pre")
            data: Event payload
        """
        event = {"event": event_type, "data": data}
        async with self._lock:
            for queue in self.queues:
                try:
                    await queue.put(event)
                except Exception as e:
                    logger.error(f"Failed to emit event to queue: {e}")

    def unsubscribe(self: "EventQueueEmitter", queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove subscriber queue.

        Args:
            queue: Queue to remove
        """
        if queue in self.queues:
            self.queues.remove(queue)
