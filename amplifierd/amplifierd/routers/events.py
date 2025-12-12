"""Global SSE event streaming endpoints.

Provides system-wide event streaming for real-time updates across projects
and sessions.
"""

import asyncio
import json
import logging
from datetime import UTC
from datetime import datetime

from fastapi import APIRouter
from sse_starlette import ServerSentEvent
from sse_starlette.sse import EventSourceResponse

from amplifierd.services.global_events import get_global_events

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
async def global_event_stream() -> EventSourceResponse:
    """Global SSE stream for system-wide events.

    Connects once and receives all daemon-wide events:
    - Session lifecycle events (created, updated)
    - Automation execution events
    - System events

    Connection lifecycle:
    - Connect: Subscribes to global event stream
    - Disconnect: Unsubscribes from stream
    - No session management - stateless subscription

    Returns:
        SSE EventSourceResponse streaming global events

    Events:
        - connected: Initial connection established
        - keepalive: Periodic heartbeat (every 30s)
        - session:created: New session created
        - session:updated: Session metadata changed
        - automation:triggered: Automation executed
        - error: Stream error occurred
    """

    async def event_generator():
        """Generate SSE events from global event stream."""
        emitter = get_global_events()
        queue = emitter.subscribe()

        try:
            # Send initial connection event
            yield ServerSentEvent(
                data=json.dumps(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                event="connected",
            )

            logger.info("Global SSE stream connected")

            # Stream events indefinitely (until disconnect)
            while True:
                try:
                    # Wait for events with timeout (allows keepalive + cancellation)
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Use ServerSentEvent with JSON-serialized data
                    yield ServerSentEvent(
                        data=json.dumps(event["data"]),
                        event=event["event"],
                    )

                except TimeoutError:
                    # Send keepalive to prevent connection timeout
                    yield ServerSentEvent(
                        data=json.dumps({"timestamp": datetime.now(UTC).isoformat()}),
                        event="keepalive",
                    )

        except asyncio.CancelledError:
            # Client disconnected (normal)
            logger.info("Global SSE stream disconnected")

        except Exception as e:
            # Stream error
            logger.error(f"Global SSE stream error: {e}")
            yield ServerSentEvent(
                data=json.dumps(
                    {
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                event="error",
            )

        finally:
            # Unsubscribe from events
            emitter.unsubscribe(queue)
            logger.info("Unsubscribed from global events")

    return EventSourceResponse(event_generator())
