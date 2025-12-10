"""Async execution runner for amplifier-core.

Handles executing user prompts and streaming responses.

Contract:
- Inputs: Session objects, user prompts, configuration data
- Outputs: Async stream of execution results
- Side Effects: Creates AmplifierSession, makes LLM calls
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from typing import Any

from ..models import Session
from ..sessions.manager import SessionManager
from ..sessions.state import add_message

if TYPE_CHECKING:
    from amplifier_core import AmplifierSession

logger = logging.getLogger(__name__)


class ExecutionRunner:
    """Async execution runner using amplifier-core.

    Manages execution lifecycle including:
    - Creating AmplifierSession instances
    - Processing user prompts
    - Streaming responses
    - Tracking execution in session state

    Example:
        >>> import asyncio
        >>> from amplifier_library.sessions import SessionManager
        >>> manager = SessionManager()
        >>> session = manager.create_session("default")
        >>> runner = ExecutionRunner(config={})
        >>> async def run():
        ...     async for chunk in runner.execute(session, "Hello"):
        ...         print(chunk, end="")
        >>> asyncio.run(run())
    """

    def __init__(
        self: "ExecutionRunner",
        session_manager: SessionManager,
        config: dict[str, Any],
        session_id: str,
    ) -> None:
        """Initialize execution runner.

        Args:
            session_manager: Session manager for loading transcript history
            config: Amplifier configuration dictionary
            session_id: Session identifier (stored separately for continuity)
        """
        self.session_manager = session_manager
        self.config = config
        self._session_id = session_id
        self._session: AmplifierSession | None = None
        self._execution_lock = asyncio.Lock()

    async def _load_transcript_history(self: "ExecutionRunner") -> list[dict[str, Any]]:
        """Load historical messages from transcript, excluding current message.

        Returns:
            List of message dicts in format {"role": str, "content": str}
            Empty list if no transcript exists or on error.

        Notes:
            Excludes the most recent message (already added to session state in execute_stream).
        """
        try:
            # Get all messages from storage
            messages = self.session_manager.get_transcript(self._session_id)

            # Convert SessionMessage objects to dict format for context
            # Exclude the last message (current user message already in state)
            if messages and len(messages) > 1:
                # Return all but the last message
                return [{"role": msg.role, "content": msg.content} for msg in messages[:-1]]
            return []

        except FileNotFoundError:
            # Fresh session, no history
            logger.debug(f"No transcript found for session {self._session_id} (fresh session)")
            return []
        except Exception as e:
            # Log but don't fail - continue with empty context
            logger.warning(f"Failed to load transcript for session {self._session_id}: {e}")
            return []

    async def _ensure_session(self: "ExecutionRunner") -> None:
        """Ensure AmplifierSession exists and is initialized.

        Creates and initializes the AmplifierSession if it doesn't exist.
        Loads conversation history from transcript into context.
        Idempotent - safe to call multiple times.
        """
        if self._session is not None:
            return

        try:
            from amplifier_core import AmplifierSession
        except ImportError as e:
            raise RuntimeError(
                "amplifier-core is required for execution. Install it with: pip install amplifier-core"
            ) from e

        from amplifier_library.storage.paths import get_share_dir
        from amplifierd.module_resolver import DaemonModuleSourceResolver

        # Create session
        self._session = AmplifierSession(self.config, session_id=self._session_id)

        # Mount resolver
        share_dir = get_share_dir()
        resolver = DaemonModuleSourceResolver(share_dir)
        await self._session.coordinator.mount("module-source-resolver", resolver)
        logger.info(f"Mounted DaemonModuleSourceResolver with share_dir={share_dir}")

        # Initialize
        await self._session.initialize()
        logger.info(f"Initialized AmplifierSession for {self._session_id}")

        # Load transcript history into context
        historical_messages = await self._load_transcript_history()
        if historical_messages:
            context = self._session.coordinator.get("context")
            if context:
                logger.info(f"Loading {len(historical_messages)} historical messages into context")
                for msg in historical_messages:
                    await context.add_message(msg)
                logger.debug(f"Context initialized with {len(historical_messages)} historical messages")
            else:
                logger.warning("No context module found - cannot load transcript history")
        else:
            logger.debug("No historical messages to load (fresh session or empty transcript)")

    async def execute(
        self: "ExecutionRunner",
        session: Session,
        user_input: str,
    ) -> str:
        """Execute user input and return response.

        Creates an AmplifierSession if needed, processes the user input,
        and returns the response. Automatically saves messages to session state.

        Note: Streaming is handled by the display_system passed to AmplifierSession,
        not at this layer. This method returns the complete response.

        Args:
            session: Session object
            user_input: User's prompt/message

        Returns:
            Complete response text

        Example:
            >>> import asyncio
            >>> from amplifier_library.sessions import SessionManager
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> runner = ExecutionRunner(config={}, session_id="session_123")
            >>> async def run():
            ...     response = await runner.execute(session, "Hello")
            ...     print(response)
            >>> asyncio.run(run())
        """
        async with self._execution_lock:
            # Add user message
            add_message(session, role="user", content=user_input)

            # Ensure session exists
            await self._ensure_session()
            assert self._session is not None  # Type guard - guaranteed by _ensure_session()

            # Execute
            try:
                response = await self._session.execute(user_input)
                if response:
                    add_message(session, role="assistant", content=response)
                return response
            except Exception as e:
                error_msg = f"Execution error: {e!s}"
                logger.error(error_msg)
                add_message(session, role="assistant", content=error_msg)
                return error_msg

    async def execute_stream(
        self: "ExecutionRunner",
        session: Session,
        user_input: str,
    ) -> AsyncIterator[str]:
        """Execute user input and stream response tokens in real-time.

        Args:
            session: Session object
            user_input: User's prompt/message

        Yields:
            Response tokens as they're generated

        Example:
            >>> async for token in runner.execute_stream(session, "Hello"):
            ...     print(token, end='', flush=True)
        """
        async with self._execution_lock:
            # Add user message
            add_message(session, role="user", content=user_input)

            # Ensure session exists
            await self._ensure_session()
            assert self._session is not None  # Type guard - guaranteed by _ensure_session()

            # Stream execution
            try:
                orchestrator = self._session.coordinator.get("orchestrator")
                if not orchestrator:
                    raise RuntimeError("No orchestrator mounted")

                context = self._session.coordinator.get("context")
                providers = self._session.coordinator.get("providers")
                tools = self._session.coordinator.get("tools") or {}
                hooks = self._session.coordinator.get("hooks")

                full_response = ""
                async for token, _iteration in orchestrator._execute_stream(
                    user_input, context, providers, tools, hooks, self._session.coordinator
                ):
                    full_response += token
                    yield token

                if full_response:
                    add_message(session, role="assistant", content=full_response)

            except Exception as e:
                error_msg = f"Execution error: {e!s}"
                logger.error(error_msg)
                add_message(session, role="assistant", content=error_msg)
                yield error_msg

    async def change_profile(self: "ExecutionRunner", new_config: dict[str, Any]) -> None:
        """Change profile by recreating AmplifierSession.

        Cleanly shuts down current session and creates new one with new profile.
        Blocks if execution is in progress.

        Args:
            new_config: New mount plan/configuration dict

        Raises:
            ValueError: If new_config missing required fields
            RuntimeError: If profile change fails
        """
        # Validate new config
        if not new_config.get("session", {}).get("orchestrator"):
            raise ValueError("New config must specify session.orchestrator")
        if not new_config.get("session", {}).get("context"):
            raise ValueError("New config must specify session.context")

        async with self._execution_lock:
            logger.info(f"Changing profile for session {self._session_id}")

            try:
                # Cleanup old session if exists
                if self._session is not None:
                    await self._session.cleanup()
                    self._session = None
                    logger.debug("Cleaned up old AmplifierSession")

                # Update config
                self.config = new_config

                # Next execute() will recreate session via _ensure_session()
                logger.info(f"Profile changed successfully for session {self._session_id}")

            except Exception as e:
                logger.error(f"Failed to change profile: {e}")
                # Leave _session as None - will recreate on next execute()
                raise RuntimeError(f"Profile change failed: {e}") from e

    async def cleanup(self: "ExecutionRunner") -> None:
        """Clean up resources.

        Should be called when done with the runner to properly
        close the AmplifierSession.

        Example:
            >>> import asyncio
            >>> runner = ExecutionRunner(config={}, session_id="session_123")
            >>> asyncio.run(runner.cleanup())
        """
        if self._session is not None:
            # AmplifierSession cleanup if needed
            self._session = None
            logger.debug("ExecutionRunner cleaned up")
