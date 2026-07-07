"""Thin async HTTP client for the opencode server API.

Wraps the endpoints lakehoused drives on a running `opencode serve` process. All
paths are rooted at the server base URL (no /v1 or /api prefix). Nearly every
endpoint accepts an optional `?directory=` query selecting the project worktree.

Contract:
- Inputs: base_url of a running opencode server, session ids, prompt text
- Outputs: parsed JSON dicts / async event stream
- Side effects: HTTP calls to the opencode server

Shapes are taken from the opencode SDK OpenAPI types (@opencode-ai/sdk):
- POST /session?directory=            body {parentID?, title?}          -> Session
- GET  /session/{id}?directory=                                          -> Session (404 if gone)
- POST /session/{id}/prompt_async?directory=  body {parts, agent?, model?, system?}
- POST /session/{id}/message?directory=       (blocking) -> {info, parts}
- POST /session/{id}/abort?directory=                                    -> bool
- POST /session/{id}/permissions/{permissionID}  body {response: once|always|reject} -> bool
- GET  /session/{id}/children?directory=                                 -> [Session]
- GET  /session/{id}/message?directory=                                  -> [{info, parts}]
- GET  /event                                    (SSE stream of Event union)
- GET  /config                                   (readiness probe)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OpencodeError(RuntimeError):
    """Raised when an opencode server call fails."""


class OpencodeClient:
    """Async wrapper over a single opencode server's HTTP API.

    One client targets one server `base_url`. It owns an httpx.AsyncClient; call
    `aclose()` when done. A `default_directory` may be supplied and is used for
    calls that don't pass an explicit `directory`.
    """

    def __init__(
        self,
        base_url: str,
        *,
        default_directory: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_directory = default_directory
        # Long timeout for prompts; the event stream uses its own (no) timeout.
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _dir_params(self, directory: str | None) -> dict[str, str]:
        d = directory or self.default_directory
        return {"directory": d} if d else {}

    # --- readiness ---------------------------------------------------------

    async def ping(self) -> bool:
        """Return True if the server responds to GET /config (readiness probe)."""
        try:
            resp = await self._client.get("/config", timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    # --- sessions ----------------------------------------------------------

    async def create_session(
        self,
        directory: str | None = None,
        *,
        title: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Create an opencode session and return the Session dict (has `id`)."""
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if parent_id is not None:
            body["parentID"] = parent_id
        resp = await self._client.post("/session", params=self._dir_params(directory), json=body)
        if resp.status_code != 200:
            raise OpencodeError(f"create_session failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def get_session(self, session_id: str, directory: str | None = None) -> dict[str, Any] | None:
        """Fetch a session by id, or None if the server no longer has it (404)."""
        resp = await self._client.get(f"/session/{session_id}", params=self._dir_params(directory))
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise OpencodeError(f"get_session failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def children(self, session_id: str, directory: str | None = None) -> list[dict[str, Any]]:
        """Return child sessions (sub-agent sessions) of a session."""
        resp = await self._client.get(f"/session/{session_id}/children", params=self._dir_params(directory))
        if resp.status_code != 200:
            raise OpencodeError(f"children failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def messages(self, session_id: str, directory: str | None = None) -> list[dict[str, Any]]:
        """Return the full persisted message history [{info, parts}] for a session."""
        resp = await self._client.get(f"/session/{session_id}/message", params=self._dir_params(directory))
        if resp.status_code != 200:
            raise OpencodeError(f"messages failed: {resp.status_code} {resp.text}")
        return resp.json()

    # --- prompting ---------------------------------------------------------

    @staticmethod
    def _prompt_body(
        text: str,
        agent: str | None,
        model: str | None,
        system: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"parts": [{"type": "text", "text": text}]}
        if agent:
            body["agent"] = agent
        # model config is {providerID, modelID}; accept "provider/model" strings.
        if model and "/" in model:
            provider_id, model_id = model.split("/", 1)
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        if system:
            body["system"] = system
        return body

    async def prompt_async(
        self,
        session_id: str,
        text: str,
        directory: str | None = None,
        *,
        agent: str | None = None,
        model: str | None = None,
        system: str | None = None,
    ) -> None:
        """Fire a turn without waiting for completion. Observe results via /event."""
        body = self._prompt_body(text, agent, model, system)
        resp = await self._client.post(
            f"/session/{session_id}/prompt_async",
            params=self._dir_params(directory),
            json=body,
        )
        if resp.status_code not in (200, 202, 204):
            raise OpencodeError(f"prompt_async failed: {resp.status_code} {resp.text}")

    async def prompt(
        self,
        session_id: str,
        text: str,
        directory: str | None = None,
        *,
        agent: str | None = None,
        model: str | None = None,
        system: str | None = None,
        timeout: float | None = 600.0,
    ) -> dict[str, Any]:
        """Blocking prompt; returns {info: AssistantMessage, parts: [...]}.

        Used for headless/automation runs that don't need token streaming.
        """
        body = self._prompt_body(text, agent, model, system)
        resp = await self._client.post(
            f"/session/{session_id}/message",
            params=self._dir_params(directory),
            json=body,
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise OpencodeError(f"prompt failed: {resp.status_code} {resp.text}")
        return resp.json()

    async def abort(self, session_id: str, directory: str | None = None) -> bool:
        """Abort the in-flight turn for a session."""
        resp = await self._client.post(f"/session/{session_id}/abort", params=self._dir_params(directory))
        if resp.status_code != 200:
            return False
        try:
            return bool(resp.json())
        except (json.JSONDecodeError, ValueError):
            return True

    async def reply_permission(
        self,
        session_id: str,
        permission_id: str,
        response: str,
        directory: str | None = None,
    ) -> bool:
        """Answer a pending permission. `response` must be once|always|reject."""
        if response not in ("once", "always", "reject"):
            raise ValueError(f"invalid permission response: {response!r}")
        resp = await self._client.post(
            f"/session/{session_id}/permissions/{permission_id}",
            params=self._dir_params(directory),
            json={"response": response},
        )
        if resp.status_code != 200:
            raise OpencodeError(f"reply_permission failed: {resp.status_code} {resp.text}")
        try:
            return bool(resp.json())
        except (json.JSONDecodeError, ValueError):
            return True

    # --- events (SSE) ------------------------------------------------------

    async def event_stream(self) -> AsyncIterator[dict[str, Any]]:
        """Yield parsed opencode Event objects from GET /global/event (SSE).

        Uses /global/event (not /event): /event is scoped to a single instance
        (directory), but one server serves many project directories, so we need the
        cross-instance stream. Each /global/event frame is {directory, payload: Event};
        we unwrap and yield the inner Event {"type", "properties"} (with `directory`
        merged in for convenience). Runs until the connection closes.

        Uses aiter_bytes() with manual SSE framing: httpx's aiter_lines() buffers
        across chunk reads and stalls on a long-lived server-push stream.
        """
        async with self._client.stream("GET", "/global/event", timeout=None) as resp:
            if resp.status_code != 200:
                raise OpencodeError(f"event_stream failed: {resp.status_code}")
            buf = ""
            data_lines: list[str] = []
            async for chunk in resp.aiter_bytes():
                buf += chunk.decode("utf-8", errors="replace")
                # SSE frames are separated by blank lines; process complete lines.
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.rstrip("\r")
                    if line == "":
                        # frame boundary -> emit accumulated data
                        if data_lines:
                            raw = "\n".join(data_lines)
                            data_lines = []
                            try:
                                frame = json.loads(raw)
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse opencode event payload: %r", raw[:200])
                                continue
                            event = frame.get("payload")
                            if isinstance(event, dict):
                                if "directory" in frame:
                                    event["directory"] = frame["directory"]
                                yield event
                        continue
                    if line.startswith(":"):
                        continue  # SSE comment/keepalive
                    if line.startswith("data:"):
                        data_lines.append(line[len("data:") :].lstrip())
                    # event:/id:/retry: field lines ignored; JSON `type` is authoritative.
