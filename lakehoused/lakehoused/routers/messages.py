"""Messages router for lakehoused API.

Handles message operations: send message, get transcript, send message for execution.
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel

from lakehoused.sessions.manager import SessionManager as SessionStateService
from lakehoused.storage import get_state_dir

from ..models import MessageResponse
from ..models import SendMessageRequest
from ..models import TranscriptResponse

logger = logging.getLogger(__name__)

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
    message_request: SendMessageRequest,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    request: Request,
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
        from datetime import UTC
        from datetime import datetime
        from pathlib import Path

        from lakehoused.config.settings import load_config
        from lakehoused.models.sessions import SessionMetadata as LibrarySessionMetadata
        from lakehoused.opencode import LakehouseOpencodeManager
        from lakehoused.opencode import OpencodeRunner
        from lakehoused.opencode import session_config
        from lakehoused.sessions.manager import SessionManager
        from lakehoused.storage import get_state_dir

        from ..services.mention_resolver import MentionResolver
        from ..services.session_stream_registry import get_stream_registry

        session = LibrarySessionMetadata(**metadata.model_dump())

        config = load_config()
        data_dir = Path(config.data_path)
        state_dir = get_state_dir()

        # Load the session's assistant config (created at session creation).
        cfg = session_config.read(session_id)
        if not cfg:
            raise HTTPException(status_code=500, detail=f"Assistant config not found for session {session_id}")

        directory = cfg.get("directory") or str(data_dir)
        project_path = Path(directory)

        # Resolve the assistant manifest and get/boot its opencode server.
        assistant_manager = LakehouseOpencodeManager(config.opencode_assistants_path or None)
        try:
            resolved = assistant_manager.resolve(cfg["assistant_name"])
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        server_registry = request.app.state.opencode_servers
        server = await server_registry.get_or_create(resolved.spec)

        # Resolve runtime @mentions (inlined by the runner as a prompt preamble).
        mention_resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )
        runtime_context_messages = mention_resolver.resolve_runtime_mentions(message_request.content)
        logger.info(f"Resolved {len(runtime_context_messages)} runtime context messages")

        # Build the project context (lakehouse primer + ancestor AGENTS.md chain, from the
        # project dir up to the data root). Delivered to opencode as the prompt `system` field.
        from ..services.project_context import build_project_context_system

        system_context = build_project_context_system(project_path, data_dir)
        if system_context:
            logger.info(f"Built project context system ({len(system_context)} chars)")

        # Get (or create) the session's stream manager (owns the emitter).
        registry = get_stream_registry()
        manager = await registry.get_or_create(session_id)

        # Build the per-turn runner. It persists the opencode session id back to
        # assistant.json when it first creates the opencode session.
        session_manager = SessionManager(state_dir)

        def _persist_ocid(ocid: str) -> None:
            session_config.set_opencode_session_id(session_id, ocid)

        runner = OpencodeRunner(
            session_manager=session_manager,
            emitter=manager.emitter,
            server=server,
            session_id=session_id,
            directory=directory,
            agent=cfg.get("agent") or resolved.default_agent,
            model=cfg.get("model") or resolved.model,
            system=system_context,
            opencode_session_id=cfg.get("opencode_session_id"),
            on_session_created=_persist_ocid,
        )

        # Emit user_message_saved to ALL subscribers (runner saves the transcript).
        await manager.emitter.emit(
            "user_message_saved",
            {"role": "user", "content": message_request.content, "timestamp": datetime.now(UTC).isoformat()},
        )

        # Emit assistant_message_start to SSE subscribers
        await manager.emitter.emit(
            "assistant_message_start",
            {"timestamp": datetime.now(UTC).isoformat()},
        )

        # Execute in background task - don't block response
        async def execute_and_emit():
            try:
                full_response = ""
                async for token in runner.execute_stream(session, message_request.content, runtime_context_messages):
                    full_response += token
                    # Emit each token to ALL subscribers
                    await manager.emitter.emit("content", {"type": "content", "content": token})

                # Note: Don't save assistant message here - ExecutionRunner.execute_stream() does it
                # to avoid duplicates in transcript

                # Emit completion to ALL subscribers
                if full_response:
                    await manager.emitter.emit(
                        "assistant_message_complete",
                        {
                            "role": "assistant",
                            "content": full_response,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )

                    # Mark session as unread so user sees badge when viewing another session
                    # Only mark unread if:
                    # 1. No one is currently viewing (no active SSE subscribers)
                    # 2. Session was previously read (avoid unnecessary writes)
                    has_active_viewers = len(manager.emitter.queues) > 0
                    if not has_active_viewers:
                        current_session = service.get_session(session_id)
                        if current_session and not current_session.is_unread:
                            service.update_session_fields(session_id, is_unread=True)
                            # Import here to avoid circular imports at module level
                            from ..models.events import SessionUpdatedEvent
                            from ..services.global_events import GlobalEventService

                            await GlobalEventService.emit(
                                SessionUpdatedEvent(
                                    project_id=current_session.project_path,
                                    session_id=session_id,
                                    fields_changed=["is_unread"],
                                )
                            )
                            logger.debug(f"Marked session {session_id} as unread after assistant response")
                    else:
                        logger.debug(f"Session {session_id} has active viewers, not marking as unread")
            except asyncio.CancelledError:
                logger.info(f"Execution cancelled for session {session_id}")
                await manager.emitter.emit(
                    "execution_cancelled",
                    {"timestamp": datetime.now(UTC).isoformat()},
                )
                raise  # Re-raise to properly terminate the task
            except Exception as e:
                logger.error(f"Execution error in background task: {e}")
                await manager.emitter.emit("execution_error", {"error": str(e)})
            finally:
                manager.clear_execution_task()

            # Start execution in background and track the task

        task = asyncio.create_task(execute_and_emit())
        manager.set_execution_task(task)

        # Return immediately
        return {"status": "executing", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send message to session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/cancel-execution", status_code=200)
async def cancel_execution(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, str]:
    """Cancel any pending execution for a session.

    This endpoint cancels the current background execution task if one is active.
    An 'execution_cancelled' event will be emitted to SSE subscribers.

    Args:
        session_id: Session ID
        service: SessionStateService dependency

    Returns:
        Status indicating whether execution was cancelled or no active execution

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        from ..services.session_stream_registry import get_stream_registry

        registry = get_stream_registry()
        manager = registry.get(session_id)

        if manager is None:
            return {"status": "no_active_execution", "session_id": session_id}

        cancelled = manager.cancel_execution()

        if cancelled:
            return {"status": "cancelled", "session_id": session_id}
        return {"status": "no_active_execution", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel execution for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/messages/last", status_code=200)
async def delete_last_message(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, str | dict | None]:
    """Delete the last message from a session's transcript.

    This endpoint removes the most recent message from the transcript.
    Cannot be called while an execution is in progress.

    Args:
        session_id: Session ID
        service: SessionStateService dependency

    Returns:
        Status and deleted message info

    Raises:
        HTTPException: 404 if session not found, 409 if execution active
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        from ..services.session_stream_registry import get_stream_registry

        registry = get_stream_registry()
        manager = registry.get(session_id)

        # Check no active execution
        if manager and manager.has_active_execution():
            raise HTTPException(
                status_code=409,
                detail="Cannot delete message while execution is active",
            )

        deleted = service.delete_last_message(session_id)

        if deleted and manager:
            # Emit SSE event for cross-client sync
            await manager.emitter.emit(
                "message_deleted",
                {
                    "position": "last",
                    "deleted_message": {
                        "role": deleted.role,
                        "content": deleted.content[:100] if len(deleted.content) > 100 else deleted.content,
                        "timestamp": deleted.timestamp.isoformat(),
                    },
                },
            )

        if deleted:
            return {
                "status": "deleted",
                "session_id": session_id,
                "deleted_message": {
                    "role": deleted.role,
                    "timestamp": deleted.timestamp.isoformat(),
                },
            }
        return {"status": "no_messages", "session_id": session_id, "deleted_message": None}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete last message for session {session_id}: {e}")
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


class ApprovalResponse(BaseModel):
    """User's response to an approval prompt (opencode permission)."""

    approval_id: str
    response: str


def _map_approval_response(label: str) -> str:
    """Map a webapp option label to an opencode permission response.

    Options offered: "Allow" -> once, "Always Allow" -> always, "Deny" -> reject.
    """
    low = label.strip().lower()
    if low.startswith("always"):
        return "always"
    if low in ("deny", "reject", "no", "decline"):
        return "reject"
    return "once"


@router.post("/approval-response")
async def submit_approval_response(
    session_id: str,
    response: ApprovalResponse,
    request: Request,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, str]:
    """Relay a user's approval decision to opencode.

    The webapp posts {approval_id, response} where approval_id is the opencode
    permission id. We look up the session's opencode server/session and reply.
    """
    from lakehoused.config.settings import load_config
    from lakehoused.opencode import LakehouseOpencodeManager
    from lakehoused.opencode import session_config

    if service.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    cfg = session_config.read(session_id)
    if not cfg or not cfg.get("opencode_session_id"):
        raise HTTPException(status_code=404, detail="No active opencode session for approval")

    config = load_config()
    assistant_manager = LakehouseOpencodeManager(config.opencode_assistants_path or None)
    try:
        resolved = assistant_manager.resolve(cfg["assistant_name"])
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    server = await request.app.state.opencode_servers.get_or_create(resolved.spec)
    mapped = _map_approval_response(response.response)
    ok = await server.client.reply_permission(
        cfg["opencode_session_id"], response.approval_id, mapped, cfg.get("directory")
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to relay approval to opencode")
    return {"status": "received", "approval_id": response.approval_id}
