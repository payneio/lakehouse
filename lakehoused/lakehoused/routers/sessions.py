"""Session lifecycle API endpoints with mount plan integration.

Manages complete session lifecycle:
- Create session (generates mount plan + creates state)
- Start/Complete/Fail/Terminate transitions
- Transcript management
- Queries and listing
"""

import json
import logging
from pathlib import Path
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field as PydanticField

from lakehoused.models.sessions import SessionMessage
from lakehoused.models.sessions import SessionMetadata
from lakehoused.models.sessions import SessionStatus
from lakehoused.sessions.manager import SessionManager as SessionStateService
from lakehoused.storage import get_state_dir

from ..models.events import SessionUpdatedEvent
from ..services.global_events import GlobalEventService

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def get_session_state_service() -> SessionStateService:
    """Get session state service instance.

    Returns:
        SessionStateService instance configured with state directory
    """
    state_dir = get_state_dir()
    return SessionStateService(storage_dir=state_dir)


# --- Request/Response Models ---


class SessionUpdateRequest(BaseModel):
    """Request model for updating session metadata."""

    name: str | None = PydanticField(None, max_length=200, description="Session name (empty string clears it)")


# --- Lifecycle Endpoints ---


@router.post("/", response_model=SessionMetadata, status_code=201)
async def create_session(
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    project_path: str = Body(".", embed=True),
    assistant_name: str | None = Body(None, embed=True),
    parent_session_id: str | None = Body(None, embed=True),
    settings_overrides: dict | None = Body(None, embed=True),
) -> SessionMetadata:
    """Create new session with mount plan.

    Generates mount plan and creates session in ACTIVE state.
    Session is immediately ready for message exchange.

    As of v0.2.0, sessions are created in ACTIVE state and are immediately
    ready for message exchange. The start_session endpoint is no longer
    required but remains for backwards compatibility.

    Args:
        project_path: Relative path to project directory (defaults to ".")
        assistant_name: Assistant to use for session (if not provided, uses directory's default_assistant)
        parent_session_id: Optional parent session for sub-sessions
        settings_overrides: Optional settings to override assistant defaults
        session_service: Session state service dependency

    Returns:
        SessionMetadata for newly created session

    Raises:
        HTTPException:
            - 400 if project_path is not a project or request is invalid
            - 404 if assistant not found
            - 500 for other errors

    Example:
        ```json
        {
            "project_path": "projects/my-project",
            "assistant_name": "software-developer",
            "parent_session_id": "parent-session-123",
            "settings_overrides": {
                "llm": {"model": "gpt-4"}
            }
        }
        ```
    """
    try:
        # Get data root from daemon config
        from pathlib import Path

        from lakehoused.config.settings import load_config

        config = load_config()
        data_path = Path(config.data_path)

        # Validate project exists
        from ..services.project_service import ProjectService

        project_service = ProjectService(data_path)

        project = project_service.get(project_path)
        if not project:
            raise HTTPException(
                status_code=400,
                detail=f"Directory '{project_path}' is not a project. Create it first using POST /api/v1/projects/",
            )

        # If no assistant specified, use directory's default_assistant (or legacy default_profile)
        if not assistant_name:
            assistant_name = project.default_assistant or project.metadata.get("default_profile")
            if not assistant_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"No assistant specified and directory '{project_path}' has no default_assistant in metadata",
                )

        # Resolve absolute paths for session metadata
        absolute_project_path = str((Path(data_path) / project_path).resolve())

        # Resolve the assistant manifest for this assistant name.
        import uuid

        from lakehoused.config.settings import load_config as load_settings
        from lakehoused.opencode import LakehouseOpencodeManager
        from lakehoused.opencode import session_config

        session_id = f"session_{uuid.uuid4().hex[:8]}"

        settings = load_settings()
        assistant_manager = LakehouseOpencodeManager(settings.opencode_assistants_path or None)
        try:
            resolved = assistant_manager.resolve(assistant_name)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Assistant '{assistant_name}' not found") from e

        # Create session (metadata + dirs). The opencode session is created lazily
        # on the first message and its id persisted back to assistant.json.
        metadata = session_service.create_session(
            session_id=session_id,
            assistant_name=assistant_name,
            parent_session_id=parent_session_id,
            project_path=project_path,
        )

        # Persist the assistant config (replaces mount_plan.json).
        session_config.write(
            session_id,
            assistant_name=assistant_name,
            manifest_hash=resolved.spec.content_hash,
            directory=absolute_project_path,
            agent=resolved.default_agent,
            model=resolved.model,
        )

        # Emit session:created event
        from ..models.events import SessionCreatedEvent

        await GlobalEventService.emit(
            SessionCreatedEvent(
                session_id=metadata.session_id,
                session_name=metadata.name,
                project_id=metadata.project_path,
                is_unread=metadata.is_unread,
                created_by="user",
            )
        )

        logger.info(f"Created session {metadata.session_id} in '{project_path}' with assistant {assistant_name}")
        return metadata

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to create session: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(exc)}") from exc


def _clone_single_session(
    source_session: SessionMetadata,
    new_parent_session_id: str | None,
    session_service: SessionStateService,
    add_copy_suffix: bool = True,
) -> SessionMetadata:
    """Clone a single session (helper function).

    Args:
        source_session: Source session metadata
        new_parent_session_id: Parent session ID for the clone (None for root)
        session_service: Session state service
        add_copy_suffix: Whether to add " (copy)" to the name

    Returns:
        Cloned session metadata
    """
    import uuid

    from lakehoused.config.settings import load_config
    from lakehoused.opencode import session_config

    state_dir = get_state_dir()
    source_session_dir = state_dir / "sessions" / source_session.session_id

    # Generate new session ID
    new_session_id = f"session_{uuid.uuid4().hex[:8]}"

    # Generate cloned name
    source_name = source_session.name or "Session"
    new_name = f"{source_name} (copy)" if add_copy_suffix else source_name

    # Get absolute project path (use data_path if no project)
    config = load_config()
    data_path = Path(config.data_path)
    if source_session.project_path:
        absolute_project_path = str((data_path / source_session.project_path).resolve())
    else:
        absolute_project_path = str(data_path.resolve())

    # Create the cloned session (metadata + dirs).
    session_service.create_session(
        session_id=new_session_id,
        assistant_name=source_session.assistant_name,
        parent_session_id=new_parent_session_id,
        project_path=source_session.project_path,
    )

    # Clone the assistant config, resetting the opencode session binding so the
    # clone starts its own opencode conversation.
    source_cfg = session_config.read(source_session.session_id) or {}
    session_config.write(
        new_session_id,
        assistant_name=source_cfg.get("assistant_name", source_session.assistant_name),
        manifest_hash=source_cfg.get("manifest_hash", ""),
        directory=source_cfg.get("directory", absolute_project_path),
        agent=source_cfg.get("agent"),
        model=source_cfg.get("model"),
        opencode_session_id=None,
    )

    new_session_dir = state_dir / "sessions" / new_session_id
    new_session_dir.mkdir(parents=True, exist_ok=True)

    # Copy transcript if it exists
    source_transcript = source_session_dir / "transcript.jsonl"
    if source_transcript.exists():
        new_transcript = new_session_dir / "transcript.jsonl"
        new_transcript.write_text(source_transcript.read_text())
        logger.debug(f"Copied transcript from {source_session.session_id} to {new_session_id}")

    # Copy events log if it exists
    source_events = source_session_dir / "events.jsonl"
    if source_events.exists():
        new_events = new_session_dir / "events.jsonl"
        new_events.write_text(source_events.read_text())
        logger.debug(f"Copied events from {source_session.session_id} to {new_session_id}")

    # Copy context messages if they exist
    source_context_file = source_session_dir / "context_messages.json"
    if source_context_file.exists():
        new_context_file = new_session_dir / "context_messages.json"
        new_context_file.write_text(source_context_file.read_text())
        logger.debug(f"Copied context messages from {source_session.session_id} to {new_session_id}")

    # Update session metadata (name and message count from source)
    def update_metadata(meta: SessionMetadata) -> None:
        meta.name = new_name
        meta.message_count = source_session.message_count
        meta.agent_invocations = source_session.agent_invocations
        meta.token_usage = source_session.token_usage

    session_service._update_session(new_session_id, update_metadata)

    updated = session_service.get_session(new_session_id)
    if updated is None:
        raise ValueError(f"Failed to retrieve cloned session {new_session_id}")
    return updated


async def _clone_session_recursive(
    source_session_id: str,
    new_parent_session_id: str | None,
    session_service: SessionStateService,
    add_copy_suffix: bool = True,
) -> SessionMetadata:
    """Recursively clone a session and all its subsessions.

    Args:
        source_session_id: Source session ID to clone
        new_parent_session_id: Parent session ID for the clone (None for root)
        session_service: Session state service
        add_copy_suffix: Whether to add " (copy)" to the name

    Returns:
        Cloned root session metadata
    """
    from ..models.events import SessionCreatedEvent

    # Get source session
    source_session = session_service.get_session(source_session_id)
    if not source_session:
        raise ValueError(f"Session {source_session_id} not found")

    # Clone this session
    cloned_session = _clone_single_session(
        source_session=source_session,
        new_parent_session_id=new_parent_session_id,
        session_service=session_service,
        add_copy_suffix=add_copy_suffix,
    )

    # Emit session:created event
    await GlobalEventService.emit(
        SessionCreatedEvent(
            session_id=cloned_session.session_id,
            session_name=cloned_session.name,
            project_id=cloned_session.project_path,
            is_unread=cloned_session.is_unread,
            created_by="user",
        )
    )

    logger.info(f"Cloned session {source_session_id} to {cloned_session.session_id}")

    # Find and clone all subsessions
    subsessions = session_service.list_sessions(parent_session_id=source_session_id)
    for subsession in subsessions:
        await _clone_session_recursive(
            source_session_id=subsession.session_id,
            new_parent_session_id=cloned_session.session_id,
            session_service=session_service,
            add_copy_suffix=False,  # Don't add (copy) to subsession names
        )

    return cloned_session


@router.post("/{session_id}/clone", response_model=SessionMetadata, status_code=201)
async def clone_session(
    session_id: str,
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> SessionMetadata:
    """Clone an existing session including transcript, events, and all subsessions.

    Creates a complete copy of an existing session including:
    - Same assistant_name and mount_plan configuration
    - Same project_path
    - Full transcript (message history)
    - Full events log
    - Profile context messages
    - All subsessions (recursively cloned)
    - New session_id
    - Name with " (copy)" suffix

    Args:
        session_id: Source session identifier to clone
        session_service: Session state service dependency

    Returns:
        SessionMetadata for newly created cloned session

    Raises:
        HTTPException:
            - 404 if source session not found
            - 500 for clone operation failures
    """
    try:
        # Check source session exists
        source_session = session_service.get_session(session_id)
        if not source_session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Recursively clone session and all subsessions
        cloned_session = await _clone_session_recursive(
            source_session_id=session_id,
            new_parent_session_id=None,  # Clone is standalone (no parent)
            session_service=session_service,
            add_copy_suffix=True,
        )

        # Count subsessions cloned
        subsession_count = len(session_service.list_sessions(parent_session_id=session_id))
        if subsession_count > 0:
            logger.info(f"Cloned {subsession_count} subsessions for {session_id}")

        return cloned_session

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to clone session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to clone session: {str(exc)}") from exc


@router.post("/{session_id}/start", status_code=204)
async def start_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> None:
    """Start session (idempotent).

    As of v0.2.0, sessions are created in ACTIVE state, making this
    endpoint redundant but kept for backwards compatibility.

    Behavior:
    - If session is ACTIVE: no-op, returns success
    - If session is CREATED: transitions to ACTIVE (legacy sessions)
    - If session is terminal: returns 400 error

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Raises:
        HTTPException:
            - 400 if session in terminal state (COMPLETED/FAILED/TERMINATED)
            - 404 if session not found
            - 500 for other errors
    """
    try:
        service.start_session(session_id)
        logger.info(f"Started session {session_id}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from exc
    except Exception as exc:
        logger.error(f"Failed to start session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/complete", status_code=204)
async def complete_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> None:
    """Complete session (ACTIVE → COMPLETED).

    Transitions session from ACTIVE to COMPLETED state. Marks successful
    completion of session.

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Raises:
        HTTPException:
            - 400 if session not in ACTIVE state
            - 404 if session not found
            - 500 for other errors
    """
    try:
        service.complete_session(session_id)
        logger.info(f"Completed session {session_id}")

        # Clean up session stream manager
        from ..services.session_stream_registry import get_stream_registry

        registry = get_stream_registry()
        await registry.cleanup_session(session_id)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from exc
    except Exception as exc:
        logger.error(f"Failed to complete session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/fail", status_code=204)
async def fail_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    error_message: str = Body(..., embed=True),
    error_details: dict | None = Body(None, embed=True),
) -> None:
    """Mark session as failed (ACTIVE → FAILED).

    Transitions session from ACTIVE to FAILED state. Records error
    information for debugging.

    Args:
        session_id: Session identifier
        error_message: Error message describing failure
        error_details: Optional additional error context
        service: Session state service dependency

    Raises:
        HTTPException:
            - 400 if session not in ACTIVE state
            - 404 if session not found
            - 500 for other errors

    Example:
        ```json
        {
            "error_message": "LLM API timeout",
            "error_details": {
                "api": "openai",
                "timeout_seconds": 30
            }
        }
        ```
    """
    try:
        service.fail_session(
            session_id=session_id,
            error_message=error_message,
            error_details=error_details,
        )
        logger.warning(f"Failed session {session_id}: {error_message}")

        # Clean up session stream manager
        from ..services.session_stream_registry import get_stream_registry

        registry = get_stream_registry()
        await registry.cleanup_session(session_id)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from exc
    except Exception as exc:
        logger.error(f"Failed to mark session {session_id} as failed: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/terminate", status_code=204)
async def terminate_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> None:
    """Terminate session (ACTIVE → TERMINATED).

    Transitions session from ACTIVE to TERMINATED state. Used when user
    kills session intentionally (e.g., Ctrl+C).

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Raises:
        HTTPException:
            - 400 if session not in ACTIVE state
            - 404 if session not found
            - 500 for other errors
    """
    try:
        service.terminate_session(session_id)
        logger.info(f"Terminated session {session_id}")

        # Clean up session stream manager
        from ..services.session_stream_registry import get_stream_registry

        registry = get_stream_registry()
        await registry.cleanup_session(session_id)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from exc
    except Exception as exc:
        logger.error(f"Failed to terminate session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# --- Query Endpoints ---


@router.get("/unread-counts", response_model=dict[str, int])
async def get_unread_counts(
    manager: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, int]:
    """Get count of unread sessions per project.

    Args:
        manager: Session state service dependency

    Returns:
        Dictionary mapping project_id to unread count
        Example: {"project/path": 3, "another/project": 1}

    Raises:
        HTTPException:
            - 500 for errors
    """
    try:
        counts: dict[str, int] = {}

        # Get all sessions
        all_sessions = manager.list_sessions()

        # Count unread sessions by project
        for session in all_sessions:
            if session.is_unread:
                # Use "_no_project" for sessions without a project
                project_id = session.project_path or "_no_project"
                counts[project_id] = counts.get(project_id, 0) + 1

        return counts

    except Exception as exc:
        logger.error(f"Failed to get unread counts: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{session_id}", response_model=SessionMetadata)
async def get_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> SessionMetadata:
    """Get session metadata.

    Retrieves complete session metadata including status, timestamps,
    and metrics.

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Returns:
        Complete session metadata

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for other errors
    """
    try:
        metadata = service.get_session(session_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return metadata
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.patch("/{session_id}", response_model=SessionMetadata)
async def update_session(
    session_id: str,
    update: SessionUpdateRequest,
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> SessionMetadata:
    """Update session metadata.

    Args:
        session_id: Session identifier
        update: Fields to update
        session_service: Session state service dependency

    Returns:
        Updated session metadata

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        # Get current session
        current = session_service.get_session(session_id)
        if not current:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Update name if provided (empty string clears it)
        if update.name is not None:
            trimmed = update.name.strip()

            def update_name(meta: SessionMetadata) -> None:
                meta.name = trimmed if trimmed else None

            session_service._update_session(session_id, update_name)

        # Return updated session
        updated = session_service.get_session(session_id)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[SessionMetadata])
async def list_sessions(
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    status: SessionStatus | None = None,
    assistant_name: str | None = None,
    project_path: str | None = None,
    limit: int | None = None,
) -> list[SessionMetadata]:
    """List sessions with optional filters.

    Returns sessions matching all provided filters (AND logic).
    Results sorted by creation time descending (most recent first).

    Args:
        status: Optional filter by session status
        assistant_name: Optional filter by assistant name
        project_path: Optional filter by project path
        limit: Optional maximum number of results
        service: Session state service dependency

    Returns:
        List of session metadata matching filters

    Raises:
        HTTPException:
            - 500 for errors

    Example:
        ```
        GET /api/v1/sessions?status=active&assistant_name=software-developer&project_path=projects/my-project&limit=10
        ```
    """
    try:
        return service.list_sessions(
            status=status,
            assistant_name=assistant_name,
            project_path=project_path,
            limit=limit,
        )
    except Exception as exc:
        logger.error(f"Failed to list sessions: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/active/list", response_model=list[SessionMetadata])
async def get_active_sessions(
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> list[SessionMetadata]:
    """Get all active sessions.

    Convenience endpoint for listing only ACTIVE sessions.

    Args:
        service: Session state service dependency

    Returns:
        List of active session metadata

    Raises:
        HTTPException:
            - 500 for errors
    """
    try:
        return service.get_active_sessions()
    except Exception as exc:
        logger.error(f"Failed to get active sessions: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# --- Transcript Endpoints ---


@router.get("/{session_id}/transcript", response_model=list[SessionMessage])
async def get_transcript(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    limit: int | None = None,
) -> list[SessionMessage]:
    """Get session transcript.

    Retrieves conversation history for session. Optionally limited to
    last N messages.

    Args:
        session_id: Session identifier
        limit: Optional maximum number of messages (most recent first)
        service: Session state service dependency

    Returns:
        List of session messages

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for other errors

    Example:
        ```
        GET /api/v1/sessions/{session_id}/transcript?limit=10
        ```
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return service.get_transcript(session_id, limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get transcript for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/messages", status_code=201)
async def append_message(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    role: str = Body(..., embed=True),
    content: str = Body(..., embed=True),
    agent: str | None = Body(None, embed=True),
    token_count: int | None = Body(None, embed=True),
) -> None:
    """Append message to session transcript.

    Adds new message to conversation history. Updates session metrics
    (message count, token usage).

    Args:
        session_id: Session identifier
        role: Message role ("user", "assistant", or "system")
        content: Message content
        agent: Optional agent identifier
        token_count: Optional token count for this message
        service: Session state service dependency

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for other errors

    Example:
        ```json
        {
            "role": "user",
            "content": "Hello, world!",
            "agent": "user",
            "token_count": 5
        }
        ```
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        service.append_message(
            session_id=session_id,
            role=role,
            content=content,
            agent=agent,
            token_count=token_count,
        )
        logger.debug(f"Appended {role} message to session {session_id}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to append message to {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# --- Read/Unread Management ---


@router.post("/{session_id}/mark-read", status_code=200)
async def mark_session_read(
    session_id: str,
    manager: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict:
    """Mark session as read.

    Called by frontend when user views session for 2+ seconds.
    Only updates if currently unread to avoid unnecessary writes.

    Args:
        session_id: Session identifier
        manager: Session state service dependency

    Returns:
        Status dictionary with session_id

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for other errors
    """
    try:
        session = manager.get_session(session_id)
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")

        # Only update if currently unread
        if session.is_unread:
            from datetime import UTC
            from datetime import datetime

            # Update metadata
            manager.update_session_fields(session_id, is_unread=False, last_read_at=datetime.now(UTC))

            # Emit global event
            await GlobalEventService.emit(
                SessionUpdatedEvent(
                    project_id=session.project_path, session_id=session_id, fields_changed=["is_unread"]
                )
            )

            logger.info(f"Marked session {session_id} as read")

        return {"status": "read", "session_id": session_id}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to mark session {session_id} as read: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# --- Management Endpoints ---


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> None:
    """Delete session and all its data.

    Permanently removes session directory including mount plan,
    metadata, and transcript. Cannot be undone.

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for other errors
    """
    try:
        if not service.delete_session(session_id):
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        logger.info(f"Deleted session {session_id}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to delete session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/cleanup", response_model=dict)
async def cleanup_old_sessions(
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    older_than_days: int = Body(30, embed=True),
) -> dict:
    """Cleanup old sessions.

    Removes sessions older than specified threshold. Active sessions
    are never removed regardless of age.

    Args:
        older_than_days: Age threshold in days (default: 30)
        service: Session state service dependency

    Returns:
        Dictionary with "removed_count" key

    Raises:
        HTTPException:
            - 500 for errors

    Example:
        ```json
        {
            "older_than_days": 60
        }
        ```

        Response:
        ```json
        {
            "removed_count": 15
        }
        ```
    """
    try:
        removed_count = service.cleanup_old_sessions(older_than_days=older_than_days)
        logger.info(f"Cleaned up {removed_count} sessions older than {older_than_days} days")
        return {"removed_count": removed_count}
    except Exception as exc:
        logger.error(f"Failed to cleanup old sessions: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{session_id}/mount-plan")
async def get_session_mount_plan(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, Any]:
    """Get the assistant config for a session.

    With the opencode backend this returns the session's assistant.json (assistant
    name, manifest hash, opencode session binding), which replaces the old mount plan.

    Raises:
        HTTPException: 404 if session or assistant config not found; 500 otherwise.
    """
    try:
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        from lakehoused.opencode import session_config

        cfg = session_config.read(session_id)
        if cfg is None:
            raise HTTPException(status_code=404, detail=f"Assistant config not found for session {session_id}")
        return cfg

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get assistant config for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{session_id}/execution-trace")
async def get_execution_trace(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> dict[str, list[dict]]:
    """Load execution trace for session.

    Aggregates trace on-the-fly from events.jsonl (single source of truth).
    Retrieves complete execution history including:
    - Tool invocations with timing and results
    - Thinking blocks
    - Sub-agent calls
    - Turn status and errors

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Returns:
        Dictionary with "turns" key containing list of execution turns

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for aggregation errors

    Example Response:
        ```json
        {
            "turns": [
                {
                    "id": "abc123",
                    "userMessage": "List files",
                    "status": "completed",
                    "startTime": 1705315800000,
                    "endTime": 1705315802500,
                    "tools": [
                        {
                            "id": "call_1",
                            "name": "Bash",
                            "status": "completed",
                            "duration": 150.0,
                            "result": "file1.txt\nfile2.txt"
                        }
                    ],
                    "thinking": []
                }
            ]
        }
        ```
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Aggregate trace on-the-fly from events.jsonl
        from ..services.trace_aggregator import aggregate_events_to_turns

        state_dir = get_state_dir()
        events_file = state_dir / "sessions" / session_id / "events.jsonl"

        turns = aggregate_events_to_turns(events_file)

        # Serialize with camelCase field names for frontend
        return {"turns": [turn.model_dump(by_alias=True) for turn in turns]}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to load execution trace for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


class SessionEventsResponse(BaseModel):
    """Response model for raw session events."""

    events: list[dict[str, Any]]
    total: int
    has_more: bool = PydanticField(alias="hasMore")

    model_config = {"populate_by_name": True}


def _read_events_from_file(events_file: Path, session_id: str) -> list[dict[str, Any]]:
    """Read events from a JSONL file and ensure session_id is present."""
    events: list[dict[str, Any]] = []
    if not events_file.exists():
        return events

    with open(events_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                # Ensure session_id is present for filtering
                if "session_id" not in event:
                    event["session_id"] = session_id
                events.append(event)
            except json.JSONDecodeError:
                # Skip malformed lines
                continue
    return events


@router.get("/{session_id}/events")
async def get_session_events(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    limit: int = 500,
    offset: int = 0,
    level: str | None = None,
    event_type: str | None = None,
    include_children: bool = False,
) -> SessionEventsResponse:
    """Get raw events from session's events.jsonl file.

    Returns events in chronological order with optional filtering.
    Useful for debugging and detailed event inspection.

    Args:
        session_id: Session identifier
        limit: Maximum events to return (default 500)
        offset: Number of events to skip (default 0)
        level: Filter by log level (INFO, DEBUG, WARNING, ERROR)
        event_type: Filter by event type prefix (e.g., "tool:", "llm:")
        include_children: If true, include events from child/subsessions

    Returns:
        SessionEventsResponse with events array, total count, and hasMore flag

    Raises:
        HTTPException:
            - 404 if session not found
            - 500 for read errors
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        state_dir = get_state_dir()
        sessions_dir = state_dir / "sessions"

        # Collect all session IDs to load events from
        session_ids_to_load = [session_id]

        if include_children:
            # Find child sessions
            child_sessions = service.list_sessions(parent_session_id=session_id)
            session_ids_to_load.extend(child.session_id for child in child_sessions)

        # Read and aggregate events from all sessions
        all_events: list[dict[str, Any]] = []
        for sid in session_ids_to_load:
            events_file = sessions_dir / sid / "events.jsonl"
            all_events.extend(_read_events_from_file(events_file, sid))

        # Sort by timestamp if we aggregated multiple sessions
        if include_children and len(session_ids_to_load) > 1:
            all_events.sort(key=lambda e: e.get("ts", ""))

        # Apply filters
        filtered_events = all_events
        if level:
            level_upper = level.upper()
            filtered_events = [e for e in filtered_events if e.get("lvl", "").upper() == level_upper]
        if event_type:
            # Support prefix matching (e.g., "tool:" matches "tool:pre", "tool:post")
            filtered_events = [e for e in filtered_events if e.get("event", "").startswith(event_type)]

        # Pagination
        total = len(filtered_events)
        paginated = filtered_events[offset : offset + limit]
        has_more = offset + limit < total

        return SessionEventsResponse(events=paginated, total=total, hasMore=has_more)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to load events for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/change-assistant", response_model=SessionMetadata)
async def change_session_assistant(
    session_id: str,
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    assistant_name: str = Body(..., embed=True),
) -> SessionMetadata:
    """Change assistant for active session.

    Waits for any in-flight execution to complete before switching.
    Session transcript and state are preserved.

    Args:
        session_id: Session identifier
        assistant_name: New assistant to use (e.g., "software-developer")
        session_service: Session state service dependency

    Returns:
        Updated session metadata

    Raises:
        HTTPException:
            - 400 if session not ACTIVE or assistant invalid
            - 404 if session or assistant not found
            - 500 for assistant change failures

    Example:
        ```json
        {
            "assistant_name": "software-developer"
        }
        ```
    """
    try:
        # 1. Validate session exists and is ACTIVE
        metadata = session_service.get_session(session_id)
        if not metadata:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if metadata.status != SessionStatus.ACTIVE:
            raise HTTPException(
                status_code=400,
                detail=f"Can only change assistant for ACTIVE sessions, this session is {metadata.status}",
            )

        # 2. Resolve the new assistant manifest.
        from lakehoused.config.settings import load_config as load_settings
        from lakehoused.opencode import LakehouseOpencodeManager
        from lakehoused.opencode import session_config

        settings = load_settings()
        data_path = Path(settings.data_path)
        if metadata.project_path:
            absolute_project_path = (data_path / metadata.project_path).resolve()
        else:
            absolute_project_path = data_path.resolve()

        assistant_manager = LakehouseOpencodeManager(settings.opencode_assistants_path or None)
        try:
            resolved = assistant_manager.resolve(assistant_name)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Assistant '{assistant_name}' not found: {e}") from e

        # 3. Rewrite assistant.json. Switching manifests means a fresh opencode
        #    session (different agent roster), so opencode_session_id resets to None.
        session_config.write(
            session_id,
            assistant_name=assistant_name,
            manifest_hash=resolved.spec.content_hash,
            directory=str(absolute_project_path),
            agent=resolved.default_agent,
            model=resolved.model,
            opencode_session_id=None,
        )

        # 4. Update session metadata.
        def update(meta: SessionMetadata) -> None:
            meta.assistant_name = assistant_name

        session_service._update_session(session_id, update)

        logger.info(f"Changed session {session_id} assistant to {assistant_name}")
        updated = session_service.get_session(session_id)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found after update")
        return updated

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error changing profile for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
