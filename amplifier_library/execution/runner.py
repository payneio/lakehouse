"""Async execution runner for amplifier-core.

Handles executing user prompts and streaming responses.

Contract:
- Inputs: Session objects, user prompts, configuration data
- Outputs: Async stream of execution results
- Side Effects: Creates AmplifierSession, makes LLM calls
"""

import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from typing import Any

from ..models import Session
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
        config: dict[str, Any],
    ) -> None:
        """Initialize execution runner.

        Args:
            config: Amplifier configuration dictionary
        """
        self.config = config
        self._session: AmplifierSession | None = None

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
            >>> runner = ExecutionRunner(config={})
            >>> async def run():
            ...     response = await runner.execute(session, "Hello")
            ...     print(response)
            >>> asyncio.run(run())
        """
        # Add user message to session state
        add_message(session, role="user", content=user_input)

        # Create AmplifierSession if needed
        if self._session is None:
            try:
                from amplifier_core import AmplifierSession
            except ImportError as e:
                raise RuntimeError(
                    "amplifier-core is required for execution. Install it with: pip install amplifier-core"
                ) from e

            from amplifier_library.storage.paths import get_share_dir
            from amplifierd.module_resolver import DaemonModuleSourceResolver

            # Create session (loader is created internally)
            self._session = AmplifierSession(self.config, session_id=session.id)

            # Mount resolver for module resolution
            share_dir = get_share_dir()
            resolver = DaemonModuleSourceResolver(share_dir)
            await self._session.coordinator.mount("module-source-resolver", resolver)
            logger.info(f"Mounted DaemonModuleSourceResolver with share_dir={share_dir}")

            # Initialize session - loader will use resolver
            await self._session.initialize()
            logger.info(f"Initialized AmplifierSession for {session.id}")

        # Execute and get response
        try:
            response = await self._session.execute(user_input)

            # Add assistant response to session state
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

        # Add user message to session state
        add_message(session, role="user", content=user_input)

        # Create AmplifierSession if needed
        if self._session is None:
            try:
                from amplifier_core import AmplifierSession
            except ImportError as e:
                raise RuntimeError(
                    "amplifier-core is required for execution. Install it with: pip install amplifier-core"
                ) from e

            from amplifier_library.storage.paths import get_share_dir
            from amplifierd.module_resolver import DaemonModuleSourceResolver

            # Create session (loader is created internally)
            self._session = AmplifierSession(self.config, session_id=session.id)

            # Mount resolver for module resolution
            share_dir = get_share_dir()
            resolver = DaemonModuleSourceResolver(share_dir)
            await self._session.coordinator.mount("module-source-resolver", resolver)
            logger.info(f"Mounted DaemonModuleSourceResolver with share_dir={share_dir}")

            # Initialize session - loader will use resolver
            await self._session.initialize()
            logger.info(f"Initialized AmplifierSession for {session.id}")

        # Get orchestrator and stream tokens
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

            # Add complete response to session state
            if full_response:
                add_message(session, role="assistant", content=full_response)

        except Exception as e:
            error_msg = f"Execution error: {e!s}"
            logger.error(error_msg)
            add_message(session, role="assistant", content=error_msg)
            yield error_msg

    async def cleanup(self: "ExecutionRunner") -> None:
        """Clean up resources.

        Should be called when done with the runner to properly
        close the AmplifierSession.

        Example:
            >>> import asyncio
            >>> runner = ExecutionRunner(config={})
            >>> asyncio.run(runner.cleanup())
        """
        if self._session is not None:
            # AmplifierSession cleanup if needed
            self._session = None
            logger.debug("ExecutionRunner cleaned up")
