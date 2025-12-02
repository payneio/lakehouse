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

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException

from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifier_library.sessions.manager import SessionManager as SessionStateService
from amplifier_library.storage import get_state_dir

from ..models.mount_plans import MountPlan
from ..services.amplified_directory_service import AmplifiedDirectoryService
from ..services.mount_plan_service import MountPlanService
from .mount_plans import get_mount_plan_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def get_session_state_service() -> SessionStateService:
    """Get session state service instance.

    Returns:
        SessionStateService instance configured with state directory
    """
    state_dir = get_state_dir()
    return SessionStateService(storage_dir=state_dir)


# --- Lifecycle Endpoints ---


@router.post("/", response_model=SessionMetadata, status_code=201)
async def create_session(
    mount_plan_service: Annotated[MountPlanService, Depends(get_mount_plan_service)],
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    amplified_dir: str = Body(".", embed=True),
    profile_name: str | None = Body(None, embed=True),
    parent_session_id: str | None = Body(None, embed=True),
    settings_overrides: dict | None = Body(None, embed=True),
) -> SessionMetadata:
    """Create new session with mount plan.

    Generates mount plan and creates session state in one operation.
    Session starts in CREATED state and must be explicitly started.

    Args:
        amplified_dir: Relative path to amplified directory (defaults to ".")
        profile_name: Profile to use for session (if not provided, uses directory's default_profile)
        parent_session_id: Optional parent session for sub-sessions
        settings_overrides: Optional settings to override profile defaults
        mount_plan_service: Mount plan service dependency
        session_service: Session state service dependency

    Returns:
        SessionMetadata for newly created session

    Raises:
        HTTPException:
            - 400 if amplified_dir is not amplified or request is invalid
            - 404 if profile not found
            - 500 for other errors

    Example:
        ```json
        {
            "amplified_dir": "projects/my-project",
            "profile_name": "foundation/base",
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

        from amplifier_library.config.loader import load_config

        config = load_config()
        data_path = Path(config.data_path)

        # Validate amplified directory exists
        amplified_service = AmplifiedDirectoryService(data_path)

        amplified_directory = amplified_service.get(amplified_dir)
        if not amplified_directory:
            raise HTTPException(
                status_code=400,
                detail=f"Directory '{amplified_dir}' is not amplified. "
                "Create it first using POST /amplified-directories/",
            )

        # If no profile specified, use directory's default_profile
        if not profile_name:
            profile_name = amplified_directory.metadata.get("default_profile")
            if not profile_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"No profile specified and directory '{amplified_dir}' has no default_profile in metadata",
                )

        # Resolve absolute paths for session metadata
        absolute_amplified_dir = str((Path(data_path) / amplified_dir).resolve())

        # Generate mount plan
        mount_plan = mount_plan_service.generate_mount_plan(profile_name, Path(absolute_amplified_dir))

        # Generate session ID
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Add session metadata to mount plan settings
        if "session" not in mount_plan:
            mount_plan["session"] = {}
        if "settings" not in mount_plan["session"]:
            mount_plan["session"]["settings"] = {}

        mount_plan["session"]["settings"]["amplified_dir"] = absolute_amplified_dir
        mount_plan["session"]["settings"]["session_cwd"] = absolute_amplified_dir  # Starts same
        mount_plan["session"]["settings"]["profile_name"] = profile_name

        # Inject working_dir into all tool configs
        # This ensures tools resolve relative paths against the session's working directory
        if "tools" in mount_plan:
            for tool in mount_plan["tools"]:
                if "config" not in tool:
                    tool["config"] = {}
                # Only set if not explicitly configured in profile
                if "working_dir" not in tool["config"]:
                    tool["config"]["working_dir"] = absolute_amplified_dir

        # Create session with mount plan
        metadata = session_service.create_session(
            session_id=session_id,
            profile_name=profile_name,
            mount_plan=mount_plan,
            parent_session_id=parent_session_id,
            amplified_dir=amplified_dir,
        )

        logger.info(f"Created session {metadata.session_id} in '{amplified_dir}' with profile {profile_name}")
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


@router.post("/{session_id}/start", status_code=204)
async def start_session(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> None:
    """Start session (CREATED → ACTIVE).

    Transitions session from CREATED to ACTIVE state. Must be called
    before messages can be exchanged.

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Raises:
        HTTPException:
            - 400 if session not in CREATED state
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


@router.get("/", response_model=list[SessionMetadata])
async def list_sessions(
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
    status: SessionStatus | None = None,
    profile_name: str | None = None,
    amplified_dir: str | None = None,
    limit: int | None = None,
) -> list[SessionMetadata]:
    """List sessions with optional filters.

    Returns sessions matching all provided filters (AND logic).
    Results sorted by creation time descending (most recent first).

    Args:
        status: Optional filter by session status
        profile_name: Optional filter by profile name
        amplified_dir: Optional filter by amplified directory path
        limit: Optional maximum number of results
        service: Session state service dependency

    Returns:
        List of session metadata matching filters

    Raises:
        HTTPException:
            - 500 for errors

    Example:
        ```
        GET /api/v1/sessions?status=active&profile_name=foundation/base&amplified_dir=projects/my-project&limit=10
        ```
    """
    try:
        return service.list_sessions(
            status=status,
            profile_name=profile_name,
            amplified_dir=amplified_dir,
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


@router.get("/{session_id}/mount-plan", response_model=MountPlan)
async def get_session_mount_plan(
    session_id: str,
    service: Annotated[SessionStateService, Depends(get_session_state_service)],
) -> MountPlan:
    """Get mount plan for session.

    Retrieves the complete mount plan that was used to initialize
    this session.

    Args:
        session_id: Session identifier
        service: Session state service dependency

    Returns:
        Complete mount plan with all resources

    Raises:
        HTTPException:
            - 404 if session or mount plan not found
            - 500 for other errors
    """
    try:
        # Check session exists
        if service.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        # Load mount plan from session directory
        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / "mount_plan.json"

        if not mount_plan_path.exists():
            raise HTTPException(status_code=404, detail=f"Mount plan not found for session {session_id}")

        # Parse and return mount plan
        mount_plan_data = json.loads(mount_plan_path.read_text())
        return MountPlan.model_validate(mount_plan_data)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get mount plan for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{session_id}/change-profile", response_model=SessionMetadata)
async def change_session_profile(
    session_id: str,
    mount_plan_service: Annotated[MountPlanService, Depends(get_mount_plan_service)],
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    profile_name: str = Body(..., embed=True),
) -> SessionMetadata:
    """Change profile for active session.

    Waits for any in-flight execution to complete before switching.
    Session transcript and state are preserved.

    Args:
        session_id: Session identifier
        profile_name: New profile to use (e.g., "foundation/base")
        mount_plan_service: Mount plan service dependency
        session_service: Session state service dependency

    Returns:
        Updated session metadata

    Raises:
        HTTPException:
            - 400 if session not ACTIVE or profile invalid
            - 404 if session or profile not found
            - 500 for profile change failures

    Example:
        ```json
        {
            "profile_name": "foundation/production"
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
                detail=f"Can only change profile for ACTIVE sessions, this session is {metadata.status}",
            )

        # 2. Generate new mount plan
        # Get absolute amplified_dir path from session metadata
        from amplifier_library.config.loader import load_config

        config = load_config()
        data_path = Path(config.data_path)
        absolute_amplified_dir = (data_path / metadata.amplified_dir).resolve()

        try:
            new_mount_plan = mount_plan_service.generate_mount_plan(profile_name, absolute_amplified_dir)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid profile '{profile_name}': {e}")
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_name}' not found: {e}")

        # Inject profile name into mount plan settings for AI awareness
        if "session" not in new_mount_plan:
            new_mount_plan["session"] = {}
        if "settings" not in new_mount_plan["session"]:
            new_mount_plan["session"]["settings"] = {}
        new_mount_plan["session"]["settings"]["profile_name"] = profile_name

        # 3. Change profile in ExecutionRunner (blocks if execution in progress)
        from ..services.session_stream_registry import change_session_profile as do_change

        try:
            await do_change(session_id, new_mount_plan)
        except ValueError:
            # No active runner - that's okay, profile will be used when session starts
            logger.info(f"No active runner for {session_id}, profile will take effect on next message")
        except Exception as e:
            logger.error(f"Profile change failed for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Profile change failed: {str(e)}")

        # 4. Persist mount plan to disk (critical for subsequent messages)
        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / "mount_plan.json"

        try:
            mount_plan_path.write_text(json.dumps(new_mount_plan, indent=2))
            logger.debug(f"Persisted new mount plan for {session_id} to {mount_plan_path}")
        except Exception as e:
            logger.error(f"Failed to persist mount plan for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to persist profile change to disk: {str(e)}")

        # 5. Update SessionStreamManager with new mount plan
        from ..services.session_stream_registry import get_stream_registry

        stream_registry = get_stream_registry()
        try:
            await stream_registry.update_mount_plan(session_id, new_mount_plan)
            logger.debug(f"Updated SessionStreamManager mount plan for {session_id}")
        except Exception as e:
            logger.warning(f"Failed to update SessionStreamManager mount plan: {e}")
            # Non-fatal - new mount plan will be used when manager is recreated

        # 6. Update session metadata
        def update(meta: SessionMetadata) -> None:
            meta.profile_name = profile_name

        session_service._update_session(session_id, update)

        logger.info(f"Changed session {session_id} profile to {profile_name}")
        updated = session_service.get_session(session_id)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found after update")
        return updated

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error changing profile for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
