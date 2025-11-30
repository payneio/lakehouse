"""Messages router for amplifierd API.

Handles message operations: send message, get transcript, send message for execution.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel

from amplifier_library.execution.runner import ExecutionRunner
from amplifier_library.sessions.manager import SessionManager as SessionStateService
from amplifier_library.storage import get_state_dir

from ..models import MessageResponse
from ..models import SendMessageRequest
from ..models import TranscriptResponse

logger = logging.getLogger(__name__)

# Keep ExecutionRunner in scope for test mocking
__test_exports__ = [ExecutionRunner]

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["messages"])


def get_session_state_service() -> SessionStateService:
    """Dependency to get SessionStateService instance.

    Returns:
        SessionStateService instance configured with state directory
    """
    state_dir = get_state_dir()
    return SessionStateService(storage_dir=state_dir)


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


@router.post("/send-message", status_code=202)
async def send_message_for_execution(
    session_id: str,
    request: SendMessageRequest,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, str]:
    """Send message and trigger execution (SSE-only architecture).

    This endpoint triggers execution and returns immediately.
    All events (user message, content, completion) are broadcast via
    SessionStreamManager to persistent /stream subscribers.

    Use this endpoint when you have a persistent /stream connection.
    Use /execute if you want direct SSE streaming without persistent connection.

    Args:
        session_id: Session ID
        request: Message request
        service: SessionStateService dependency

    Returns:
        Status confirmation

    Raises:
        HTTPException: 404 if session not found, 500 on error
    """
    try:
        # Check session exists
        metadata = service.get_session(session_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Convert to library SessionMetadata
        import json
        from datetime import UTC
        from datetime import datetime

        from amplifier_library.models.sessions import SessionMetadata as LibrarySessionMetadata
        from amplifier_library.storage import get_state_dir

        from ..services.session_stream_registry import get_stream_registry

        session = LibrarySessionMetadata(**metadata.model_dump())

        # Load mount plan
        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / metadata.mount_plan_path

        if not mount_plan_path.exists():
            raise HTTPException(status_code=500, detail=f"Mount plan not found: {metadata.mount_plan_path}")

        with open(mount_plan_path) as f:
            mount_plan = json.load(f)

        # Get stream manager (creates if needed)
        registry = get_stream_registry()
        manager = await registry.get_or_create(session_id, mount_plan)

        # Emit user_message_saved to ALL subscribers
        await manager.emitter.emit(
            "user_message_saved",
            {"role": "user", "content": request.content, "timestamp": datetime.now(UTC).isoformat()},
        )

        # Save user message
        service.append_message(session_id=session_id, role="user", content=request.content)

        # Get runner
        runner = await manager.get_runner(session)

        # Mount hooks if needed
        if runner._session is not None:
            await manager.mount_hooks(runner)

        # Emit assistant_message_start
        await manager.emitter.emit(
            "assistant_message_start",
            {"timestamp": datetime.now(UTC).isoformat()},
        )

        # Execute in background task - don't block response
        async def execute_and_emit():
            try:
                full_response = ""
                async for token in runner.execute_stream(session, request.content):
                    full_response += token
                    # Emit each token to ALL subscribers
                    await manager.emitter.emit("content", {"type": "content", "content": token})

                # Save assistant response
                if full_response:
                    service.append_message(session_id=session_id, role="assistant", content=full_response)

                    # Emit completion
                    await manager.emitter.emit(
                        "assistant_message_complete",
                        {
                            "role": "assistant",
                            "content": full_response,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
            except Exception as e:
                logger.error(f"Execution error in background task: {e}")
                await manager.emitter.emit("execution_error", {"error": str(e)})

        # Start execution in background
        asyncio.create_task(execute_and_emit())

        # Return immediately
        return {"status": "executing", "session_id": session_id}

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


# Approval management (in-memory for simplicity)
pending_approvals: dict[str, asyncio.Event] = {}
approval_responses: dict[str, str] = {}


class ApprovalResponse(BaseModel):
    """User's response to approval prompt."""

    approval_id: str
    response: str


@router.post("/approval-response")
async def submit_approval_response(
    session_id: str,
    response: ApprovalResponse,
) -> dict[str, str]:
    """Receive user's approval decision.

    Unblocks execution waiting on approval.

    Args:
        session_id: Session identifier
        response: User's approval response

    Returns:
        Status confirmation

    Raises:
        HTTPException: If approval not found or expired
    """
    if response.approval_id not in pending_approvals:
        raise HTTPException(status_code=404, detail="Approval not found or expired")

    # Store response
    approval_responses[response.approval_id] = response.response

    # Signal waiting execution
    pending_approvals[response.approval_id].set()

    return {"status": "received", "approval_id": response.approval_id}
