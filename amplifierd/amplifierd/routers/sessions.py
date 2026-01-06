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

import yaml
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
from ..services.amplified_directory_service import AmplifiedDirectoryService
from ..services.bundle_service import BundleService
from ..services.global_events import GlobalEventService
from .mount_plans import get_bundle_service

logger = logging.getLogger(__name__)


def _inject_runtime_config(mount_plan: dict[str, Any], session_id: str, amplified_dir: str) -> None:
    """Inject runtime configuration into mount plan.

    Modifies mount_plan in-place to add runtime-specific configuration that
    cannot be known at profile compilation time:
    - working_dir for tools (derived from amplified_dir)
    - allowed_write_paths for tool-filesystem (derived from amplified_dir)
    - session_log_template for hooks-logging (points to amplifierd session dir)
    - api_key for providers (from secrets.yaml)

    Args:
        mount_plan: Mount plan to modify (modified in-place)
        session_id: Session identifier for path templates
        amplified_dir: Absolute path to amplified directory
    """
    # 1. Inject working_dir into tool configs
    # This ensures tools resolve relative paths against the session's working directory
    if "tools" in mount_plan:
        for tool in mount_plan["tools"]:
            if "config" not in tool:
                tool["config"] = {}
            # Only set if not explicitly configured in profile
            if "working_dir" not in tool["config"]:
                tool["config"]["working_dir"] = amplified_dir

            # 1b. Inject allowed_write_paths for tool-filesystem if not explicitly set
            # tool-filesystem defaults to ["."] which resolves against daemon CWD, not working_dir
            # This ensures write operations are allowed within the session's working directory
            tool_module = tool.get("module", "") or tool.get("id", "")
            is_filesystem_tool = "tool-filesystem" in tool_module or "filesystem" in tool.get("source", "")
            if is_filesystem_tool and "allowed_write_paths" not in tool["config"]:
                tool["config"]["allowed_write_paths"] = [amplified_dir]

    # 2. Inject session_log_template for hooks-logging
    # This ensures events.jsonl is written to amplifierd's session directory
    # instead of the default ~/.amplifier/projects/... path
    state_dir = get_state_dir()
    session_log_path = str(state_dir / "sessions" / "{session_id}" / "events.jsonl")

    if "hooks" in mount_plan:
        for hook in mount_plan["hooks"]:
            # Mount plans use "module" key, but some may use "id"
            hook_id = hook.get("module", "") or hook.get("id", "")
            # Match hooks-logging by module/id or by checking the source
            if hook_id == "hooks-logging" or "hooks-logging" in hook.get("source", ""):
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


def _generate_profile_context_messages(
    profile_name: str, compiled_profile_dir: Path, amplified_dir: Path, data_dir: Path
) -> list[ContextMessage]:
    """Generate profile context messages from profile + behavior instructions.

    Args:
        profile_name: Name of the profile
        compiled_profile_dir: Directory containing compiled profile
        amplified_dir: Amplified directory path for mention resolution
        data_dir: Data directory path for security validation

    Returns:
        List of context messages from resolved at-mentions
    """
    try:
        from amplifierd.services.mention_resolver import MentionResolver

        # Load profile YAML to get instructions and behaviors
        profile_yaml_path = compiled_profile_dir / "profile.yaml"
        if not profile_yaml_path.exists():
            logger.debug(f"Profile YAML not found at {profile_yaml_path}")
            return []

        profile_yaml = yaml.safe_load(profile_yaml_path.read_text())

        # Start with profile instructions
        all_instructions = []
        profile_instructions = profile_yaml.get("instructions", "")
        if profile_instructions:
            all_instructions.append(profile_instructions)
            logger.debug("Loaded profile instructions")

        # Load behavior instructions
        behaviors_list = profile_yaml.get("behaviors", [])
        behavior_count = 0
        for behavior_ref in behaviors_list:
            behavior_id = behavior_ref.get("id") if isinstance(behavior_ref, dict) else behavior_ref
            if not behavior_id:
                continue

            # Try loading behavior YAML from compiled profile
            behavior_dir = compiled_profile_dir / "behaviors" / str(behavior_id)
            behavior_yaml_path = behavior_dir / "behavior.yaml"

            if not behavior_yaml_path.exists():
                # Try alternative name
                behavior_yaml_path = behavior_dir / f"{behavior_id}.yaml"

            if behavior_yaml_path.exists():
                behavior_yaml = yaml.safe_load(behavior_yaml_path.read_text())
                behavior_instructions = behavior_yaml.get("instructions", "")
                if behavior_instructions:
                    all_instructions.append(behavior_instructions)
                    behavior_count += 1
                    logger.debug(f"Loaded instructions from behavior: {behavior_id}")
            else:
                logger.debug(f"Behavior YAML not found for: {behavior_id}")

        logger.info(f"Loaded instructions from profile + {behavior_count}/{len(behaviors_list)} behaviors")

        # Resolve mentions if any instructions found
        if all_instructions:
            resolver = MentionResolver(
                compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir, data_dir=data_dir
            )
            combined_instructions = "\n\n".join(all_instructions)
            profile_context_messages = resolver.resolve_profile_instructions(combined_instructions)
            logger.info(f"Resolved {len(profile_context_messages)} context messages from profile instructions")
            return profile_context_messages

        return []

    except Exception as e:
        # Log error but don't fail - profile context is optional
        logger.error(f"Failed to generate profile context messages for {profile_name}: {e}", exc_info=True)
        return []


@router.post("/", response_model=SessionMetadata, status_code=201)
async def create_session(
    bundle_service: Annotated[BundleService, Depends(get_bundle_service)],
    session_service: Annotated[SessionStateService, Depends(get_session_state_service)],
    amplified_dir: str = Body(".", embed=True),
    profile_name: str | None = Body(None, embed=True),
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

        # Load bundle and prepare mount plan
        prepared_bundle = await bundle_service.load_bundle(profile_name)
        mount_plan = bundle_service.get_mount_plan(prepared_bundle)

        # Bundle instructions are handled by PreparedBundle's system prompt factory
        # No need for separate profile_context_messages - bundles handle @mentions internally
        profile_context_messages: list[ContextMessage] = []

        # Generate session ID
        import uuid

        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Add session metadata to mount plan settings
        if "session" not in mount_plan:
            mount_plan["session"] = {}
        if "settings" not in mount_plan["session"]:
            mount_plan["session"]["settings"] = {}

        mount_plan["session"]["settings"]["amplified_dir"] = absolute_amplified_dir
        mount_plan["session"]["settings"]["profile_name"] = profile_name

        # Inject runtime configuration (working_dir for tools, session_log_template for hooks-logging)
        _inject_runtime_config(mount_plan, session_id, absolute_amplified_dir)

        # Create session with mount plan
        metadata = session_service.create_session(
            session_id=session_id,
            profile_name=profile_name,
            mount_plan=mount_plan,
            parent_session_id=parent_session_id,
            amplified_dir=amplified_dir,
        )

        # Save profile context messages to session directory
        if profile_context_messages:
            session_dir = session_service.storage_dir / session_id
            context_file = session_dir / "profile_context_messages.json"
            context_file.write_text(
                json.dumps([msg.model_dump() for msg in profile_context_messages], indent=2), encoding="utf-8"
            )
            logger.info(f"Saved {len(profile_context_messages)} profile context messages to session {session_id}")

        # Emit session:created event
        from ..models.events import SessionCreatedEvent

        await GlobalEventService.emit(
            SessionCreatedEvent(
                session_id=metadata.session_id,
                session_name=metadata.name,
                project_id=metadata.amplified_dir,
                is_unread=metadata.is_unread,
                created_by="user",
            )
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

    # Get absolute amplified_dir path
    config = load_config()
    data_path = Path(config.data_path)
    absolute_amplified_dir = str((data_path / source_session.amplified_dir).resolve())

    # Inject runtime configuration for new session
    _inject_runtime_config(source_mount_plan, new_session_id, absolute_amplified_dir)

    # Create new session with cloned mount plan
    session_service.create_session(
        session_id=new_session_id,
        profile_name=source_session.profile_name,
        mount_plan=source_mount_plan,
        parent_session_id=new_parent_session_id,
        amplified_dir=source_session.amplified_dir,
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

    # Copy profile context messages if they exist
    source_context_file = source_session_dir / "profile_context_messages.json"
    if source_context_file.exists():
        new_context_file = new_session_dir / "profile_context_messages.json"
        new_context_file.write_text(source_context_file.read_text())
        logger.debug(f"Copied profile context messages from {source_session.session_id} to {new_session_id}")

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
            project_id=cloned_session.amplified_dir,
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
    - Same profile_name and mount_plan configuration
    - Same amplified_dir
    - Full transcript (message history)
    - Full events log
    - Profile context messages
    - All subsessions (recursively cloned)
    - New session_id
    - Name with " (copy)" suffix

    Args:
        session_id: Source session identifier to clone
        mount_plan_service: Mount plan service dependency
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
                project_id = session.amplified_dir
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
                    project_id=session.amplified_dir, session_id=session_id, fields_changed=["is_unread"]
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


@router.post("/{session_id}/change-profile", response_model=SessionMetadata)
async def change_session_profile(
    session_id: str,
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

        # 2. Generate new mount plan using BundleService
        # Get absolute amplified_dir path from session metadata
        from amplifier_library.config.loader import load_config

        config = load_config()
        data_path = Path(config.data_path)
        absolute_amplified_dir = (data_path / metadata.amplified_dir).resolve()

        # Load bundle and get mount plan
        bundle_service = get_bundle_service()
        try:
            prepared = await bundle_service.load_bundle(profile_name)
            new_mount_plan = bundle_service.get_mount_plan(prepared)
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

        # Inject runtime configuration (working_dir for tools, session_log_template for hooks-logging)
        _inject_runtime_config(new_mount_plan, session_id, str(absolute_amplified_dir))

        # 3. Regenerate profile context messages for new profile
        from amplifier_library.storage.paths import get_profiles_dir

        new_compiled_profile_dir = get_profiles_dir() / profile_name
        profile_context_messages = _generate_profile_context_messages(
            profile_name, new_compiled_profile_dir, absolute_amplified_dir, data_path
        )

        # Save to session directory (wrapped with mount plan persistence below for error handling)

        # 4. Change profile in ExecutionRunner (blocks if execution in progress)
        from ..services.session_stream_registry import change_session_profile as do_change

        try:
            await do_change(session_id, new_mount_plan)
        except ValueError:
            # No active runner - that's okay, profile will be used when session starts
            logger.info(f"No active runner for {session_id}, profile will take effect on next message")
        except Exception as e:
            logger.error(f"Profile change failed for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Profile change failed: {str(e)}")

        # 5. Persist mount plan and profile context to disk (critical for subsequent messages)
        state_dir = get_state_dir()
        mount_plan_path = state_dir / "sessions" / session_id / "mount_plan.json"
        context_file = state_dir / "sessions" / session_id / "profile_context_messages.json"

        try:
            # Write mount plan
            mount_plan_path.write_text(json.dumps(new_mount_plan, indent=2))
            logger.debug(f"Persisted new mount plan for {session_id} to {mount_plan_path}")

            # Write or remove profile context messages
            if profile_context_messages:
                context_file.write_text(json.dumps([msg.model_dump() for msg in profile_context_messages], indent=2))
                logger.info(f"Updated {len(profile_context_messages)} profile context messages for profile switch")
            else:
                # Remove old cache if new profile has no mentions
                if context_file.exists():
                    context_file.unlink()
                    logger.info("Removed profile context messages (new profile has none)")
        except Exception as e:
            logger.error(f"Failed to persist profile change for {session_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to persist profile change to disk: {str(e)}")

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
