"""OpencodeRunner: drives one lakehouse session's chat turns via opencode.

Replaces execution.runner.ExecutionRunner (which drove amplifier-core). Same
`execute_stream(session, user_input, runtime_context_messages)` async-token
signature so routers/messages.py is largely unchanged: it yields assistant text
tokens (which the caller emits as `content`) while emitting tool/thinking/approval
hook events directly to the session's EventQueueEmitter, translated from the
opencode /global/event stream. Conversation history is persisted by opencode
server-side, so there is no transcript replay.

Contract:
- Inputs: an OpencodeServer (for the assistant's manifest), project directory,
  agent/model, optional existing opencode session id
- Outputs: async stream of assistant text tokens; hook events on the emitter;
  transcript + events.jsonl side-writes
- Side effects: creates/uses an opencode session; HTTP calls to the server
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from ..sessions.state import add_message
from .events import TurnState
from .events import error_message
from .events import translate

if TYPE_CHECKING:
    from ..models.sessions import SessionMetadata
    from ..sessions.manager import SessionManager
    from ..streaming import EventQueueEmitter
    from .server_manager import OpencodeServer

logger = logging.getLogger(__name__)


class OpencodeRunner:
    """Async turn driver for one lakehouse session backed by an opencode server."""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        emitter: EventQueueEmitter,
        server: OpencodeServer,
        session_id: str,
        directory: str,
        agent: str | None = None,
        model: str | None = None,
        opencode_session_id: str | None = None,
        on_session_created: Callable[[str], None] | None = None,
    ) -> None:
        self.session_manager = session_manager
        self._emitter = emitter
        self._server = server
        self._session_id = session_id
        self._directory = directory
        self._agent = agent
        self._model = model
        self._ocid = opencode_session_id
        self._on_session_created = on_session_created
        self._execution_lock = asyncio.Lock()

    @property
    def opencode_session_id(self) -> str | None:
        return self._ocid

    # --- opencode session lifecycle ---------------------------------------

    async def _ensure_opencode_session(self) -> None:
        client = self._server.client
        assert client is not None
        if self._ocid:
            existing = await client.get_session(self._ocid, self._directory)
            if existing is not None:
                return
            logger.info("opencode session %s gone; creating a fresh one", self._ocid)
            self._ocid = None
        session = await client.create_session(directory=self._directory, title=f"lakehouse {self._session_id}")
        self._ocid = session["id"]
        if self._on_session_created:
            self._on_session_created(self._ocid)
        logger.info("Created opencode session %s for lakehouse session %s", self._ocid, self._session_id)

    def _build_prompt(self, user_input: str, ctx_messages: list[Any] | None) -> str:
        """Inline runtime @mention messages as a preamble to the user text."""
        if not ctx_messages:
            return user_input
        preambles: list[str] = []
        for m in ctx_messages:
            content = getattr(m, "content", None)
            if content is None and isinstance(m, dict):
                content = m.get("content")
            if content:
                preambles.append(str(content))
        if not preambles:
            return user_input
        return "\n\n".join(preambles) + "\n\n" + user_input

    # --- events.jsonl trace -----------------------------------------------

    def _trace(self, out_type: str, data: dict[str, Any]) -> None:
        try:
            events_path = Path(self.session_manager.storage_dir) / self._session_id / "events.jsonl"
            record = {
                "event": data.get("hook_event", out_type),
                "ts": datetime.now(UTC).isoformat(),
                "data": data.get("hook_data", data),
                "session_id": self._ocid,
            }
            with open(events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.debug("Failed to write events.jsonl: %s", e)

    # --- turn execution ----------------------------------------------------

    async def execute_stream(
        self,
        session: SessionMetadata,
        user_input: str,
        runtime_context_messages: list[Any] | None = None,
    ) -> AsyncIterator[str]:
        """Run one turn; yield assistant text tokens as they stream."""
        async with self._execution_lock:
            add_message(session, role="user", content=user_input)
            await self._ensure_opencode_session()
            assert self._ocid is not None
            client = self._server.client
            assert client is not None

            # Project context (AGENTS.md chain + @mentions) is injected by the opencode
            # `agent_context` plugin, not here. This path only inlines the user's runtime
            # @mentions as a preamble to their message.
            prompt = self._build_prompt(user_input, runtime_context_messages)
            queue = self._server.subscribe(self._ocid)
            state = TurnState()
            full_response = ""
            try:
                await client.prompt_async(
                    self._ocid,
                    prompt,
                    self._directory,
                    agent=self._agent,
                    model=self._model,
                )
                while True:
                    event = await queue.get()
                    etype = event.get("type")
                    ev_sid = event.get("properties", {}).get("sessionID")
                    if etype == "session.idle" and ev_sid == self._ocid:
                        break
                    if etype == "session.error" and ev_sid == self._ocid:
                        msg = error_message(event.get("properties", {}))
                        raise RuntimeError(msg)
                    for out_type, data in translate(event, state):
                        self._trace(out_type, data)
                        if out_type == "content":
                            token = data["content"]
                            full_response += token
                            yield token
                        else:
                            await self._emitter.emit(out_type, data)
            except asyncio.CancelledError:
                await self._safe_abort()
                raise
            finally:
                self._server.unsubscribe(self._ocid)

            if full_response:
                add_message(session, role="assistant", content=full_response)

    async def _safe_abort(self) -> None:
        if not self._ocid or self._server.client is None:
            return
        try:
            await self._server.client.abort(self._ocid, self._directory)
        except Exception as e:  # noqa: BLE001
            logger.debug("abort failed: %s", e)

    async def change_profile(
        self,
        *,
        server: OpencodeServer,
        agent: str | None,
        model: str | None,
        directory: str | None = None,
    ) -> None:
        """Switch this session to a different assistant (manifest/agent/model).

        A new manifest means a different opencode server and agent roster, so we
        bind a fresh opencode session (created lazily on the next turn).
        """
        async with self._execution_lock:
            self._server = server
            self._agent = agent
            self._model = model
            if directory is not None:
                self._directory = directory
            self._ocid = None
            logger.info("Switched assistant for session %s", self._session_id)

    async def cleanup(self) -> None:
        # The opencode session persists server-side; nothing to tear down here.
        pass
