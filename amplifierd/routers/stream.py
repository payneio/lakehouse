"""SSE stream endpoint for persistent session streaming.

Provides long-lived SSE connections for receiving session events.
"""

import asyncio
import json
import logging
from datetime import UTC
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sse_starlette.event import ServerSentEvent
from sse_starlette.sse import EventSourceResponse

from amplifier_library.sessions.manager import SessionManager as SessionStateService
from amplifier_library.storage import get_state_dir

from ..services.session_stream_registry import get_stream_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def get_session_state_service() -> SessionStateService:
    """Get session state service instance.

    Returns:
        SessionStateService instance configured with state directory
    """
    state_dir = get_state_dir()
    return SessionStateService(storage_dir=state_dir)


@router.get("/{session_id}/stream")
async def stream_session_events(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> EventSourceResponse:
    """Persistent SSE stream for session events.

    Connects once and receives all session events:
    - Hook events (tool:pre, tool:post, thinking, approvals)
    - Status changes (future)
    - Execution lifecycle events

    Works alongside /send-message endpoint which triggers execution.

    Connection lifecycle:
    - Connect: Creates/reuses SessionStreamManager
    - Disconnect: Keeps manager alive for reconnection
    - Session end: Manager cleaned up by lifecycle endpoints

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Returns:
        SSE EventSourceResponse streaming session events

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 if mount plan not found or other errors

    Events:
        - connected: Initial connection established
        - keepalive: Periodic heartbeat (every 30s)
        - hook:*: Hook events from execution
        - error: Stream error occurred
    """
    # Validate session exists
    metadata = service.get_session(session_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    # Load mount plan
    state_dir = get_state_dir()
    mount_plan_path = state_dir / "sessions" / session_id / "mount_plan.json"

    if not mount_plan_path.exists():
        raise HTTPException(status_code=500, detail=f"Mount plan not found for session {session_id}")

    with open(mount_plan_path) as f:
        mount_plan = json.load(f)

    async def event_generator():
        """Generate SSE events from session stream."""
        registry = get_stream_registry()
        manager = await registry.get_or_create(session_id, mount_plan)

        # Subscribe to event stream
        queue = manager.subscribe()

        try:
            # Send initial connection event using ServerSentEvent for proper JSON serialization
            yield ServerSentEvent(
                data=json.dumps(
                    {
                        "session_id": session_id,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                ),
                event="connected",
            )

            logger.info(f"SSE stream connected for session {session_id}")

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
            logger.info(f"SSE stream disconnected for session {session_id}")

        except Exception as e:
            # Stream error
            logger.error(f"SSE stream error for {session_id}: {e}")
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
            manager.unsubscribe(queue)
            logger.info(f"Unsubscribed from events for session {session_id}")

    return EventSourceResponse(event_generator())
