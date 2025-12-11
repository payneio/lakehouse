"""Agent spawning with configuration overlays and session hierarchy.

This module spawns child agent sessions with merged configurations
and manages the session hierarchy. Child sessions inherit parent
configuration with agent-specific overlays applied.

Contract:
- Input: Parent session, agent name, instruction, agent configs
- Output: Agent execution result with session ID for resumption
- Side Effects: Creates child sessions, persists state, executes agents

Example:
    >>> from amplifier_library.sessions import SessionManager
    >>> from amplifier_library.sessions.spawner import spawn_agent
    >>>
    >>> manager = SessionManager(Path(".amplifierd/state"))
    >>> parent_session = ... # existing session
    >>> agent_configs = {"bug-hunter": {"session": {"tools": ["debug"]}}}
    >>>
    >>> result = await spawn_agent(
    ...     parent_session=parent_session,
    ...     agent_name="bug-hunter",
    ...     instruction="Find bugs in auth.py",
    ...     agent_configs=agent_configs,
    ...     session_manager=manager
    ... )
    >>> print(result["output"])
    >>> print(result["session_id"])  # Use this to resume later
"""

import logging
import uuid
from typing import Any

from amplifier_library.models.sessions import SessionStatus

logger = logging.getLogger(__name__)


class AgentNotFoundError(ValueError):
    """Raised when requested agent doesn't exist in agent_configs."""

    pass


class ExecutionError(RuntimeError):
    """Raised when agent execution fails."""

    pass


class SessionNotFoundError(RuntimeError):
    """Raised when attempting to resume non-existent session."""

    pass


def _generate_child_session_id(parent_id: str, agent_name: str) -> str:
    """Generate W3C trace context style child session ID.

    Creates hierarchical IDs like: {parent-span}-{child-span}_{agent-name}

    Args:
        parent_id: Parent session ID
        agent_name: Name of agent being spawned

    Returns:
        Child session ID with trace hierarchy

    Example:
        >>> _generate_child_session_id("abc123", "bug-hunter")
        'abc123-f4e5d6c7b8a9_{bug-hunter}'
    """
    child_span = uuid.uuid4().hex[:16]
    return f"{parent_id}-{child_span}_{agent_name}"


def _merge_configs(parent_config: dict[str, Any], agent_config: dict[str, Any]) -> dict[str, Any]:
    """Merge parent config with agent-specific overlay.

    Uses simple deep merge strategy:
    - Nested dicts are merged recursively
    - Lists from agent_config replace parent lists (no concatenation)
    - Agent values override parent values at leaf nodes

    Args:
        parent_config: Parent session configuration
        agent_config: Agent-specific overlay configuration

    Returns:
        Merged configuration dictionary

    Example:
        >>> parent = {"session": {"orchestrator": "default", "timeout": 30}}
        >>> agent = {"session": {"tools": ["debug"]}}
        >>> merged = _merge_configs(parent, agent)
        >>> merged["session"]["orchestrator"]  # Inherited
        'default'
        >>> merged["session"]["tools"]  # From agent
        ['debug']
    """
    merged = parent_config.copy()

    for key, value in agent_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # Recursively merge nested dicts
            merged[key] = _merge_configs(merged[key], value)
        else:
            # Override or add value
            merged[key] = value

    return merged


async def spawn_agent(
    parent_session: Any,  # amplifier_library.models.Session
    agent_name: str,
    instruction: str,
    agent_configs: dict[str, dict[str, Any]],
    session_manager: Any,  # amplifier_library.sessions.SessionManager
    sub_session_id: str | None = None,
) -> dict[str, Any]:
    """Spawn child agent session with configuration overlay.

    Creates a child session with merged parent+agent config, executes
    the agent with given instruction, and returns results. Child session
    is persisted and can be resumed later.

    Args:
        parent_session: Parent AmplifierSession with existing config
        agent_name: Name of agent to spawn (must exist in agent_configs)
        instruction: Task instruction for the agent
        agent_configs: Dict mapping agent names to their config overlays
        session_manager: SessionManager for persistence
        sub_session_id: Optional custom session ID (auto-generated if None)

    Returns:
        Dictionary with:
        - output (str): Agent execution result
        - session_id (str): Child session ID for resumption
        - trace_id (str): W3C trace context ID
        - status (str): "completed", "interrupted", or "error"

    Raises:
        AgentNotFoundError: Agent name not in agent_configs
        ExecutionError: Agent execution failed
        ValueError: Invalid parent session or config

    Example:
        >>> parent_session = ... # existing session
        >>> agent_configs = {
        ...     "bug-hunter": {
        ...         "session": {
        ...             "tools": ["debug", "test"],
        ...             "context": "focused"
        ...         }
        ...     }
        ... }
        >>>
        >>> result = await spawn_agent(
        ...     parent_session=parent_session,
        ...     agent_name="bug-hunter",
        ...     instruction="Find bugs in auth.py",
        ...     agent_configs=agent_configs,
        ...     session_manager=manager
        ... )
        >>>
        >>> if result["status"] == "completed":
        ...     print(result["output"])
        ... elif result["status"] == "error":
        ...     print(f"Error: {result['output']}")
    """
    # Validate agent exists
    if agent_name not in agent_configs:
        available = ", ".join(agent_configs.keys())
        raise AgentNotFoundError(f"Agent '{agent_name}' not found in agent_configs. Available: {available}")

    # Get parent config
    parent_config = getattr(parent_session, "config", {})
    if not parent_config:
        raise ValueError("Parent session has no config")

    # Merge parent config with agent overlay
    agent_config = agent_configs[agent_name]
    merged_config = _merge_configs(parent_config, agent_config)

    # Generate child session ID if not provided
    parent_id = getattr(parent_session, "session_id", str(uuid.uuid4()))
    child_id = sub_session_id or _generate_child_session_id(parent_id, agent_name)
    trace_id = child_id  # Child ID serves as trace ID

    # Get parent's amplified directory
    parent_amplified_dir = getattr(parent_session, "amplified_dir", ".")

    logger.info(f"Spawning agent '{agent_name}' as child of {parent_id}: {child_id}")

    # Create child session in state manager
    try:
        session_manager.create_session(
            session_id=child_id,
            profile_name=agent_name,
            mount_plan=merged_config,
            parent_session_id=parent_id,
            amplified_dir=parent_amplified_dir,
        )
    except ValueError as e:
        # Session already exists - this is OK for resumption
        logger.debug(f"Child session {child_id} already exists: {e}")

    # Start session
    try:
        session_manager.start_session(child_id)
    except ValueError:
        # Already started - this is OK for resumption
        logger.debug(f"Child session {child_id} already started")

    # Import amplifier_core
    try:
        from amplifier_core import AmplifierSession
    except ImportError as e:
        raise ExecutionError(
            "amplifier-core is required for agent spawning. Install it with: pip install amplifier-core"
        ) from e

    # Import module resolver
    try:
        from amplifierd.module_resolver import DaemonModuleSourceResolver

        from amplifier_library.storage.paths import get_share_dir
    except ImportError as e:
        raise ExecutionError("Could not import required modules for agent execution") from e

    # Create and initialize AmplifierSession
    child_session = None
    try:
        # Create session
        child_session = AmplifierSession(merged_config, session_id=child_id)

        # Mount resolver
        share_dir = get_share_dir()
        resolver = DaemonModuleSourceResolver(share_dir)
        await child_session.coordinator.mount("module-source-resolver", resolver)

        # Initialize
        await child_session.initialize()
        logger.info(f"Initialized child session {child_id}")

        # Add user instruction to session
        session_manager.append_message(child_id, role="user", content=instruction)

        # Execute
        logger.info(f"Executing agent '{agent_name}' with instruction: {instruction[:100]}...")
        output = await child_session.execute(instruction)

        # Add assistant response to session
        session_manager.append_message(child_id, role="assistant", content=output or "")

        # Mark session as completed
        session_manager.complete_session(child_id)

        logger.info(f"Agent '{agent_name}' completed successfully")

        return {
            "output": output or "",
            "session_id": child_id,
            "trace_id": trace_id,
            "status": "completed",
        }

    except KeyboardInterrupt:
        # User interrupted - mark as terminated
        logger.info(f"Agent '{agent_name}' interrupted by user")
        session_manager.terminate_session(child_id)

        return {
            "output": "Agent execution interrupted by user",
            "session_id": child_id,
            "trace_id": trace_id,
            "status": "interrupted",
        }

    except Exception as e:
        # Execution failed - mark as failed
        error_msg = f"Agent '{agent_name}' execution failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        session_manager.fail_session(
            child_id,
            error_message=error_msg,
            error_details={"exception": str(e), "type": type(e).__name__},
        )

        return {
            "output": error_msg,
            "session_id": child_id,
            "trace_id": trace_id,
            "status": "error",
        }

    finally:
        # Cleanup
        if child_session is not None:
            try:
                await child_session.cleanup()
                logger.debug(f"Cleaned up child session {child_id}")
            except Exception as e:
                logger.warning(f"Error during child session cleanup: {e}")


async def resume_spawned_agent(
    session_id: str,
    instruction: str,
    session_manager: Any,  # amplifier_library.sessions.SessionManager
) -> dict[str, Any]:
    """Resume previously spawned agent session.

    Loads the child session's state (config, transcript) and continues
    execution with new instruction. Session must exist and be resumable.

    Args:
        session_id: Child session ID from previous spawn_agent call
        instruction: New task instruction for resumed agent
        session_manager: SessionManager for persistence

    Returns:
        Same format as spawn_agent:
        - output (str): Agent execution result
        - session_id (str): Same session ID
        - trace_id (str): Same trace ID
        - status (str): "completed", "interrupted", or "error"

    Raises:
        SessionNotFoundError: Session doesn't exist
        ExecutionError: Resumption failed

    Example:
        >>> # After spawn_agent returned session_id="abc-def_bug-hunter"
        >>> result = await resume_spawned_agent(
        ...     session_id="abc-def_bug-hunter",
        ...     instruction="Now check user.py for similar bugs",
        ...     session_manager=manager
        ... )
        >>> print(result["output"])
    """
    # Load session metadata
    metadata = session_manager.get_session(session_id)
    if metadata is None:
        raise SessionNotFoundError(f"Session {session_id} not found. Cannot resume non-existent session.")

    # Validate session is resumable
    if metadata.status == SessionStatus.FAILED:
        logger.warning(f"Resuming FAILED session {session_id}")
    elif metadata.status == SessionStatus.COMPLETED:
        logger.info(f"Resuming COMPLETED session {session_id}")

    # Load mount plan
    session_dir = session_manager.storage_dir / session_id
    mount_plan_path = session_dir / "mount_plan.json"

    if not mount_plan_path.exists():
        raise SessionNotFoundError(f"Session {session_id} has no mount_plan.json. Cannot resume.")

    import json

    merged_config = json.loads(mount_plan_path.read_text())

    # Extract agent name from session_id (format: parent-span_{agent_name})
    agent_name = session_id.split("_")[-1] if "_" in session_id else "resumed-agent"

    # Start session (or re-start if completed/failed)
    try:
        # Reset to active state
        def reset_to_active(meta: Any) -> None:
            meta.status = SessionStatus.ACTIVE
            meta.started_at = meta.started_at  # Keep original start time
            meta.ended_at = None  # Clear end time

        session_manager._update_session(session_id, reset_to_active)
    except Exception as e:
        logger.warning(f"Could not reset session {session_id} to active: {e}")

    # Import amplifier_core
    try:
        from amplifier_core import AmplifierSession
    except ImportError as e:
        raise ExecutionError(
            "amplifier-core is required for agent resumption. Install it with: pip install amplifier-core"
        ) from e

    # Import module resolver
    try:
        from amplifierd.module_resolver import DaemonModuleSourceResolver

        from amplifier_library.storage.paths import get_share_dir
    except ImportError as e:
        raise ExecutionError("Could not import required modules for agent execution") from e

    # Create and initialize AmplifierSession
    child_session = None
    try:
        # Create session
        child_session = AmplifierSession(merged_config, session_id=session_id)

        # Mount resolver
        share_dir = get_share_dir()
        resolver = DaemonModuleSourceResolver(share_dir)
        await child_session.coordinator.mount("module-source-resolver", resolver)

        # Initialize
        await child_session.initialize()
        logger.info(f"Initialized resumed session {session_id}")

        # Load transcript history into context
        transcript = session_manager.get_transcript(session_id)
        if transcript:
            context = child_session.coordinator.get("context")
            if context:
                logger.info(f"Loading {len(transcript)} historical messages into context")
                for msg in transcript:
                    await context.add_message({"role": msg.role, "content": msg.content})
            else:
                logger.warning("No context module - cannot load transcript history")

        # Add new user instruction
        session_manager.append_message(session_id, role="user", content=instruction)

        # Execute
        logger.info(f"Resuming agent '{agent_name}' with: {instruction[:100]}...")
        output = await child_session.execute(instruction)

        # Add assistant response
        session_manager.append_message(session_id, role="assistant", content=output or "")

        # Mark as completed
        session_manager.complete_session(session_id)

        logger.info(f"Resumed agent '{agent_name}' completed successfully")

        return {
            "output": output or "",
            "session_id": session_id,
            "trace_id": session_id,  # Session ID serves as trace ID
            "status": "completed",
        }

    except KeyboardInterrupt:
        # User interrupted
        logger.info(f"Resumed agent '{agent_name}' interrupted by user")
        session_manager.terminate_session(session_id)

        return {
            "output": "Agent execution interrupted by user",
            "session_id": session_id,
            "trace_id": session_id,
            "status": "interrupted",
        }

    except Exception as e:
        # Execution failed
        error_msg = f"Resumed agent '{agent_name}' execution failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        session_manager.fail_session(
            session_id,
            error_message=error_msg,
            error_details={"exception": str(e), "type": type(e).__name__},
        )

        return {
            "output": error_msg,
            "session_id": session_id,
            "trace_id": session_id,
            "status": "error",
        }

    finally:
        # Cleanup
        if child_session is not None:
            try:
                await child_session.cleanup()
                logger.debug(f"Cleaned up resumed session {session_id}")
            except Exception as e:
                logger.warning(f"Error during resumed session cleanup: {e}")
