"""Messages router for amplifierd API.

Handles message operations: send message, get transcript, execute with streaming.
"""

import logging
import re
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sse_starlette.sse import EventSourceResponse

from amplifier_library.execution.runner import ExecutionRunner
from amplifier_library.models import Session
from amplifier_library.storage import get_state_dir

from ..models import MessageResponse
from ..models import SendMessageRequest
from ..models import TranscriptResponse
from ..services.session_state_service import SessionStateService
from ..streaming import sse_event_stream
from ..streaming import wrap_execution_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["messages"])


def get_session_state_service() -> SessionStateService:
    """Dependency to get SessionStateService instance.

    Returns:
        SessionStateService instance configured with state directory
    """
    state_dir = get_state_dir()
    return SessionStateService(state_dir=state_dir)


@router.post("/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> MessageResponse:
    """Send a message to a session (synchronous).

    This endpoint adds a user message to the session transcript without
    executing it. Use the /execute endpoint for execution with streaming.

    Args:
        session_id: Session ID
        request: Message request
        service: SessionStateService dependency

    Returns:
        Created message

    Raises:
        HTTPException: 404 if session not found, 500 on error
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Add user message to transcript
        service.append_message(
            session_id=session_id,
            role="user",
            content=request.content,
        )

        # Get the last message we just added
        from datetime import UTC
        from datetime import datetime

        return MessageResponse(
            role="user",
            content=request.content,
            timestamp=datetime.now(UTC),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send message to session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/messages", response_model=TranscriptResponse)
async def get_messages(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> TranscriptResponse:
    """Get session transcript.

    Args:
        session_id: Session ID
        service: SessionStateService dependency

    Returns:
        Session transcript with all messages

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Get transcript
        messages = service.get_transcript(session_id)

        return TranscriptResponse(
            session_id=session_id,
            messages=[
                MessageResponse(
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp,
                )
                for msg in messages
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transcript for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/execute")
async def execute_with_streaming(
    session_id: str,
    request: SendMessageRequest,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> EventSourceResponse:
    """Execute user input with SSE streaming.

    This endpoint executes the user input and streams the response using
    Server-Sent Events (SSE).

    Args:
        session_id: Session ID
        request: Message/execution request
        service: SessionStateService dependency

    Returns:
        SSE EventSourceResponse with execution events

    Raises:
        HTTPException: 404 if session not found

    Events:
        - message: Content chunks during execution
        - done: Execution completed successfully
        - error: Execution failed with error
    """
    try:
        # Check session exists
        metadata = service.get_session(session_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Convert SessionMetadata to amplifier_library Session object
        from datetime import UTC
        from datetime import datetime

        session = Session(
            id=session_id,
            profile=metadata.profile_name,
            context={},
            created_at=metadata.created_at,
            updated_at=datetime.now(UTC),
            message_count=metadata.message_count,
        )

        # Load mount plan from session directory
        import json

        from amplifier_library.storage import get_state_dir

        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / metadata.mount_plan_path

        if not mount_plan_path.exists():
            raise HTTPException(status_code=500, detail=f"Mount plan not found: {metadata.mount_plan_path}")

        with open(mount_plan_path) as f:
            mount_plan = json.load(f)

        # Create execution runner with mount plan
        # ExecutionRunner uses DaemonModuleSourceResolver which handles profile hints
        # (e.g., "source": "foundation/base") and resolves module paths automatically
        logger.info(f"Creating ExecutionRunner for session {session_id}")
        runner = ExecutionRunner(config=mount_plan)

        # Create async generator for streaming
        async def event_generator():
            """Generate SSE events from execution."""
            try:
                # Add user message to transcript first
                service.append_message(
                    session_id=session_id,
                    role="user",
                    content=request.content,
                )

                # Use streaming method to get real-time tokens
                token_stream = runner.execute_stream(session, request.content)
                event_stream = wrap_execution_stream(token_stream)

                # Accumulate response content
                full_response = ""

                # Convert to SSE format
                async for event_str in sse_event_stream(event_stream):
                    # Parse the event to extract content if it's a message event
                    if '"type": "content"' in event_str:
                        # Extract content from JSON data
                        match = re.search(r"data: ({.*})", event_str)
                        if match:
                            data = json.loads(match.group(1))
                            if data.get("type") == "content":
                                full_response += data.get("content", "")

                    yield event_str

                # After streaming completes, save assistant response
                if full_response:
                    service.append_message(
                        session_id=session_id,
                        role="assistant",
                        content=full_response,
                    )

                # Note: Session state is also saved by ExecutionRunner.execute_stream

            except Exception as e:
                logger.error(f"Execution error in session {session_id}: {e}")
                # Yield error event with proper JSON formatting
                error_data = json.dumps({"type": "error", "error": str(e)})
                yield f"event: error\ndata: {error_data}\n\n"

        return EventSourceResponse(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute in session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
