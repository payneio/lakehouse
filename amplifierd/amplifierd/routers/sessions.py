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

from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifier_library.sessions.manager import SessionManager as SessionStateService
from amplifier_library.storage import get_state_dir

from ..models.context_messages import ContextMessage
from ..models.events import SessionUpdatedEvent
from ..models.mount_plans import MountPlan
from ..services.global_events import GlobalEventService

logger = logging.getLogger(__name__)


def _inject_runtime_config(mount_plan: dict[str, Any], session_id: str, project_path: str) -> None:
    """Inject runtime configuration into mount plan.

    Modifies mount_plan in-place to add runtime-specific configuration that
    cannot be known at profile compilation time:
    - working_dir for tools (derived from project_path)
    - allowed_write_paths for tool-filesystem (derived from project_path)
    - session_log_template for hooks-logging (points to amplifierd session dir)
    - api_key for providers (from secrets.yaml)

    Args:
        mount_plan: Mount plan to modify (modified in-place)
        session_id: Session identifier for path templates
        project_path: Absolute path to project directory
    """
    # 1. Inject working_dir into tool configs
    # This ensures tools resolve relative paths against the session's working directory
    if "tools" in mount_plan:
        for tool in mount_plan["tools"]:
            if "config" not in tool:
                tool["config"] = {}
            # Only set if not explicitly configured in profile
            if "working_dir" not in tool["config"]:
                tool["config"]["working_dir"] = project_path

            # 1b. Inject allowed_write_paths for tool-filesystem if not explicitly set
            # tool-filesystem defaults to ["."] which resolves against daemon CWD, not working_dir
            # This ensures write operations are allowed within the session's working directory
            tool_module = tool.get("module", "") or tool.get("id", "")
            is_filesystem_tool = "tool-filesystem" in tool_module or "filesystem" in tool.get("source", "")
            if is_filesystem_tool and "allowed_write_paths" not in tool["config"]:
                tool["config"]["allowed_write_paths"] = [project_path]

    # 2. Inject session_log_template for hooks-logging
    # This ensures events.jsonl is written to amplifierd's session directory
    # instead of the default ~/.amplifier/projects/... path
    state_dir = get_state_dir()
    session_log_path = str(state_dir / "sessions" / "{session_id}" / "events.jsonl")

    if "hooks" in mount_plan:
        for hook in mount_plan["hooks"]:
            # Mount plans use "module" key, but some may use "id"
            hook_id = hook.get("module", "") or hook.get("id", "")
            # Match hooks-logging/hook-logging by module/id or by checking the source
            # Note: Module name changed from hooks-logging (plural) to hook-logging (singular)
            # in the Foundation bundle system, so we check for both
            source = hook.get("source", "")
            is_logging_hook = (
                hook_id in ("hooks-logging", "hook-logging") or "hooks-logging" in source or "hook-logging" in source
            )
            if is_logging_hook:
                if "config" not in hook:
                    hook["config"] = {}
                # Always override to ensure logs go to amplifierd session dir
                hook["config"]["session_log_template"] = session_log_path
                logger.debug(f"Injected session_log_template for hooks-logging: {session_log_path}")

    # 3. Inject API keys for providers from secrets.yaml
    # This allows users to configure API keys via UI without modifying profiles
    # Priority: profile config > secrets.yaml > environment variables (handled by provider)
    if "providers" in mount_plan:
        from ..config.loader import load_secrets

        secrets = load_secrets()
        if secrets.api_keys:
            for provider in mount_plan["providers"]:
                if "config" not in provider:
                    provider["config"] = {}
                # Only inject if not already set in profile
                if "api_key" not in provider["config"]:
                    # Try module name first (e.g., "provider-anthropic")
                    provider_id = provider.get("module", "") or provider.get("id", "")
                    api_key = secrets.api_keys.get(provider_id)
                    if api_key:
                        provider["config"]["api_key"] = api_key
                        logger.debug(f"Injected API key for provider: {provider_id}")


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


def _get_lakehouse_context() -> str:
    """Load lakehouse-specific context from share directory.

    If the file doesn't exist in share dir, creates it from the default
    template bundled with the daemon.

    Returns:
        Lakehouse context string, or empty string if unavailable
    """
    try:
        from amplifier_library.storage import get_share_dir

        share_dir = get_share_dir()
        lakehouse_context_file = share_dir / "lakehouse.md"

        # If user's lakehouse.md doesn't exist, create from default
        if not lakehouse_context_file.exists():
            default_file = Path(__file__).parent.parent / "context" / "lakehouse_default.md"
            if default_file.exists():
                share_dir.mkdir(parents=True, exist_ok=True)
                lakehouse_context_file.write_text(
                    default_file.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                logger.info(f"Created lakehouse context from default: {lakehouse_context_file}")
            else:
                logger.warning("No default lakehouse context found")
                return ""

        return lakehouse_context_file.read_text(encoding="utf-8")
    except Exception as e:
        # In test environments, get_share_dir may return a Mock or other non-Path
        # Log and continue without lakehouse context
        logger.debug(f"Could not load lakehouse context: {e}")
        return ""


def _generate_bundle_context_messages(
    instruction: str | None,
    project_path: Path,
    data_dir: Path,
) -> list[ContextMessage]:
    """Generate bundle context messages from instruction.

    Automatically prepends lakehouse-specific context to ensure users
    always have context about how Lakehouse works.

    Args:
        instruction: The composed bundle instruction (from markdown body)
        project_path: Project directory for @mention resolution
        data_dir: Data directory for security validation

    Returns:
        List of context messages with resolved @mentions
    """
    # Prepend lakehouse context to bundle instruction
    lakehouse_context = _get_lakehouse_context()
    full_instruction = lakehouse_context
    if instruction:
        full_instruction += "\n\n" + instruction

    if not full_instruction.strip():
        logger.debug("No context to resolve")
        return []

    try:
        from amplifierd.services.mention_resolver import MentionResolver

        # Use project_path for @mention resolution - bundle instructions should
        # resolve @mentions relative to the project, not the bundle directory
        resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )
        bundle_context_messages = resolver.resolve_profile_instructions(full_instruction)
        logger.info(
            f"Resolved {len(bundle_context_messages)} context messages "
            f"(lakehouse: {len(lakehouse_context)} chars, bundle: {len(instruction or '')} chars)"
        )
        return bundle_context_messages
    except Exception as e:
        logger.error(f"Failed to resolve bundle instructions: {e}", exc_info=True)
        return []


@router.post("/", response_model=SessionMetadata, status_code=201)
async def create_session(
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    project_path: str = Body(".", embed=True),
    bundle_name: str | None = Body(None, embed=True),
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
        bundle_name: Bundle to use for session (if not provided, uses directory's default_bundle)
        parent_session_id: Optional parent session for sub-sessions
        settings_overrides: Optional settings to override bundle defaults
        session_service: Session state service dependency

    Returns:
        SessionMetadata for newly created session

    Raises:
        HTTPException:
            - 400 if project_path is not a project or request is invalid
            - 404 if bundle not found
            - 500 for other errors

    Example:
        ```json
        {
            "project_path": "projects/my-project",
            "bundle_name": "software-developer",
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

        # Validate project exists
        from ..services.project_service import ProjectService

        project_service = ProjectService(data_path)

        project = project_service.get(project_path)
        if not project:
            raise HTTPException(
                status_code=400,
                detail=f"Directory '{project_path}' is not a project. Create it first using POST /api/v1/projects/",
            )

        # If no bundle specified, use directory's default_bundle (or legacy default_profile)
        if not bundle_name:
            bundle_name = project.metadata.get("default_bundle") or project.metadata.get("default_profile")
            if not bundle_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"No bundle specified and directory '{project_path}' has no default_bundle in metadata",
                )

        # Resolve absolute paths for session metadata
        absolute_project_path = str((Path(data_path) / project_path).resolve())

        # Generate mount plan using bundle manager
        from amplifier_library.bundles import LakehouseBundleManager

        from ..startup import get_registry_bundles

        bundle_manager = LakehouseBundleManager(registry_bundles=get_registry_bundles())

        # Generate session ID early (needed for mount plan generation)
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Load secrets for API key injection
        from ..config.loader import load_secrets

        secrets = load_secrets()
        # Use first available API key (simplified - could be enhanced per-provider)
        api_key = next(iter(secrets.api_keys.values()), None) if secrets.api_keys else None

        mount_plan = await bundle_manager.generate_mount_plan(
            bundle_ref=bundle_name,
            session_id=session_id,
            project_path=absolute_project_path,
            api_key=api_key,
        )

        # Resolve bundle instruction mentions (from mount_plan instruction field)
        bundle_context_messages = _generate_bundle_context_messages(
            instruction=mount_plan.get("instruction"),
            project_path=Path(absolute_project_path),
            data_dir=data_path,
        )

        # Add session metadata to mount plan settings
        if "session" not in mount_plan:
            mount_plan["session"] = {}
        if "settings" not in mount_plan["session"]:
            mount_plan["session"]["settings"] = {}

        mount_plan["session"]["settings"]["project_path"] = absolute_project_path
        mount_plan["session"]["settings"]["bundle_name"] = bundle_name

        # Note: Runtime config (working_dir, allowed_write_paths, API keys, log paths)
        # is already injected by bundle_manager.generate_mount_plan()

        # Create session with mount plan
        metadata = session_service.create_session(
            session_id=session_id,
            bundle_name=bundle_name,
            mount_plan=mount_plan,
            parent_session_id=parent_session_id,
            project_path=project_path,
        )

        # Save bundle context messages to session directory
        if bundle_context_messages:
            session_dir = session_service.storage_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            context_file = session_dir / "bundle_context_messages.json"
            context_file.write_text(
                json.dumps([msg.model_dump() for msg in bundle_context_messages], indent=2), encoding="utf-8"
            )
            logger.info(f"Saved {len(bundle_context_messages)} bundle context messages to session {session_id}")

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

        logger.info(f"Created session {metadata.session_id} in '{project_path}' with bundle {bundle_name}")
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

    from amplifier_library.config.loader import load_config

    state_dir = get_state_dir()
    source_session_dir = state_dir / "sessions" / source_session.session_id
    source_mount_plan_path = source_session_dir / "mount_plan.json"

    if not source_mount_plan_path.exists():
        raise ValueError(f"Mount plan not found for session {source_session.session_id}")

    source_mount_plan = json.loads(source_mount_plan_path.read_text())

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

    # Inject runtime configuration for new session
    _inject_runtime_config(source_mount_plan, new_session_id, absolute_project_path)

    # Create new session with cloned mount plan
    session_service.create_session(
        session_id=new_session_id,
        bundle_name=source_session.bundle_name,
        mount_plan=source_mount_plan,
        parent_session_id=new_parent_session_id,
        project_path=source_session.project_path,
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

    # Copy bundle context messages if they exist
    source_context_file = source_session_dir / "bundle_context_messages.json"
    if source_context_file.exists():
        new_context_file = new_session_dir / "bundle_context_messages.json"
        new_context_file.write_text(source_context_file.read_text())
        logger.debug(f"Copied bundle context messages from {source_session.session_id} to {new_session_id}")

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
    - Same bundle_name and mount_plan configuration
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
    bundle_name: str | None = None,
    project_path: str | None = None,
    limit: int | None = None,
) -> list[SessionMetadata]:
    """List sessions with optional filters.

    Returns sessions matching all provided filters (AND logic).
    Results sorted by creation time descending (most recent first).

    Args:
        status: Optional filter by session status
        bundle_name: Optional filter by bundle name
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
        GET /api/v1/sessions?status=active&bundle_name=software-developer&project_path=projects/my-project&limit=10
        ```
    """
    try:
        return service.list_sessions(
            status=status,
            bundle_name=bundle_name,
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


@router.post("/{session_id}/change-bundle", response_model=SessionMetadata)
async def change_session_bundle(
    session_id: str,
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    bundle_name: str = Body(..., embed=True),
) -> SessionMetadata:
    """Change bundle for active session.

    Waits for any in-flight execution to complete before switching.
    Session transcript and state are preserved.

    Args:
        session_id: Session identifier
        bundle_name: New bundle to use (e.g., "software-developer")
        session_service: Session state service dependency

    Returns:
        Updated session metadata

    Raises:
        HTTPException:
            - 400 if session not ACTIVE or bundle invalid
            - 404 if session or bundle not found
            - 500 for bundle change failures

    Example:
        ```json
        {
            "bundle_name": "software-developer"
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
                detail=f"Can only change bundle for ACTIVE sessions, this session is {metadata.status}",
            )

        # 2. Generate new mount plan using bundle manager
        from amplifier_library.bundles import LakehouseBundleManager
        from amplifier_library.config.loader import load_config

        from ..startup import get_registry_bundles

        config = load_config()
        data_path = Path(config.data_path)
        # Use data_path if no project
        if metadata.project_path:
            absolute_project_path = (data_path / metadata.project_path).resolve()
        else:
            absolute_project_path = data_path.resolve()

        bundle_manager = LakehouseBundleManager(registry_bundles=get_registry_bundles())

        # Load secrets for API key injection
        from ..config.loader import load_secrets

        secrets = load_secrets()
        api_key = next(iter(secrets.api_keys.values()), None) if secrets.api_keys else None

        try:
            new_mount_plan = await bundle_manager.generate_mount_plan(
                bundle_ref=bundle_name,
                session_id=session_id,
                project_path=str(absolute_project_path),
                api_key=api_key,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid bundle '{bundle_name}': {e}")
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Bundle '{bundle_name}' not found: {e}")

        # Inject bundle name into mount plan settings for AI awareness
        if "session" not in new_mount_plan:
            new_mount_plan["session"] = {}
        if "settings" not in new_mount_plan["session"]:
            new_mount_plan["session"]["settings"] = {}
        new_mount_plan["session"]["settings"]["bundle_name"] = bundle_name

        # Note: Runtime config (working_dir, allowed_write_paths, API keys, log paths)
        # is already injected by bundle_manager.generate_mount_plan()

        # 3. Regenerate bundle context messages for new bundle (from mount_plan instruction)
        bundle_context_messages = _generate_bundle_context_messages(
            instruction=new_mount_plan.get("instruction"),
            project_path=absolute_project_path,
            data_dir=data_path,
        )

        # Save to session directory (wrapped with mount plan persistence below for error handling)

        # 4. Change bundle in ExecutionRunner (blocks if execution in progress)
        from ..services.session_stream_registry import change_session_profile as do_change

        try:
            await do_change(session_id, new_mount_plan)
        except ValueError:
            # No active runner - that's okay, bundle will be used when session starts
            logger.info(f"No active runner for {session_id}, bundle will take effect on next message")
        except Exception as e:
            logger.error(f"Bundle change failed for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Bundle change failed: {str(e)}")

        # 5. Persist mount plan and bundle context to disk (critical for subsequent messages)
        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / "mount_plan.json"
        context_file = state_dir / "sessions" / session_id / "bundle_context_messages.json"

        try:
            # Write mount plan
            mount_plan_path.write_text(json.dumps(new_mount_plan, indent=2))
            logger.debug(f"Persisted new mount plan for {session_id} to {mount_plan_path}")

            # Write or remove bundle context messages
            if bundle_context_messages:
                context_file.write_text(json.dumps([msg.model_dump() for msg in bundle_context_messages], indent=2))
                logger.info(f"Updated {len(bundle_context_messages)} bundle context messages for bundle switch")
            else:
                # Remove old cache if new bundle has no mentions
                if context_file.exists():
                    context_file.unlink()
                    logger.info("Removed bundle context messages (new bundle has none)")
        except Exception as e:
            logger.error(f"Failed to persist bundle change for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to persist bundle change to disk: {str(e)}")

        # 6. Update SessionStreamManager with new mount plan
        from ..services.session_stream_registry import get_stream_registry

        stream_registry = get_stream_registry()
        try:
            await stream_registry.update_mount_plan(session_id, new_mount_plan)
            logger.debug(f"Updated SessionStreamManager mount plan for {session_id}")
        except Exception as e:
            logger.warning(f"Failed to update SessionStreamManager mount plan: {e}")
            # Non-fatal - new mount plan will be used when manager is recreated

        # 7. Update session metadata
        def update(meta: SessionMetadata) -> None:
            meta.bundle_name = bundle_name

        session_service._update_session(session_id, update)

        logger.info(f"Changed session {session_id} bundle to {bundle_name}")
        updated = session_service.get_session(session_id)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found after update")
        return updated

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Unexpected error changing profile for {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
