"""Pooled `opencode serve` process lifecycle.

Topology: one opencode server per distinct manifest (assistant), shared across all
lakehouse sessions and project directories using it. Config (provider keys + agent
roster) is fixed at server boot via a scrubbed env + OPENCODE_CONFIG; `directory`
is per-session/per-request. Keyed by (manifest_name, content_hash) so editing a
manifest transparently spins a fresh server and retires the stale one.

Each server holds ONE long-lived GET /event subscription and demultiplexes events
to per-session queues by sessionID, routing descendant (sub-agent) session events to
the subscribed root so a turn observes its whole subtree.

Contract:
- Inputs: ManifestSpec (name, hash, manifest path, agent_lib, referenced env vars)
- Outputs: OpencodeServer with a ready base_url + client and per-session event queues
- Side effects: spawns/kills `opencode serve` subprocesses
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import socket
import time
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from ..storage.paths import get_log_dir
from .client import OpencodeClient

logger = logging.getLogger(__name__)

# Env vars always forwarded to the server (never provider keys).
_BASE_ENV_KEYS = ("PATH", "HOME", "TERM", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "USER")

_ENV_REF_RE = re.compile(r"\{env:([A-Z0-9_]+)\}")


def extract_env_var_names(manifest_text: str) -> set[str]:
    """Return the set of {env:VAR} names referenced by a manifest's text."""
    return set(_ENV_REF_RE.findall(manifest_text))


def build_server_env(manifest_path: Path, agent_lib: Path, referenced_env_vars: set[str]) -> dict[str, str]:
    """Build a scrubbed env for an opencode server.

    opencode auto-instantiates a provider for EVERY API-key env var it sees and can
    crash on a stray/broken one, so we forward only the {env:VAR} names the manifest
    references (plus AGENT_LIB, OPENCODE_CONFIG, and a /v1-only ANTHROPIC_BASE_URL).
    """
    env: dict[str, str] = {k: os.environ[k] for k in _BASE_ENV_KEYS if k in os.environ}
    env["AGENT_LIB"] = str(agent_lib)
    env["OPENCODE_CONFIG"] = str(manifest_path)
    for var in referenced_env_vars:
        if var in os.environ:
            env[var] = os.environ[var]
    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    if "/v1" in base:
        env["ANTHROPIC_BASE_URL"] = base
    return env


def _prealloc_port() -> int:
    """Pre-allocate a free localhost port (small TOCTOU race, acceptable)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


@dataclass
class ManifestSpec:
    """Everything needed to boot an opencode server for one assistant manifest."""

    name: str
    content_hash: str
    manifest_path: Path
    agent_lib: Path
    referenced_env_vars: set[str] = field(default_factory=set)

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.content_hash)


def _event_session_id(event: dict[str, Any]) -> str | None:
    """Extract the sessionID an opencode Event pertains to, if any."""
    props = event.get("properties")
    if not isinstance(props, dict):
        return None
    # Direct sessionID (session.*, permission.*, todo.*, message.part.removed, ...)
    sid = props.get("sessionID")
    if isinstance(sid, str):
        return sid
    # session.created / session.updated carry {info: Session}
    info = props.get("info")
    if isinstance(info, dict):
        if isinstance(info.get("sessionID"), str):
            return info["sessionID"]
        if isinstance(info.get("id"), str):
            return info["id"]
    # message.part.updated carries {part: Part}
    part = props.get("part")
    if isinstance(part, dict) and isinstance(part.get("sessionID"), str):
        return part["sessionID"]
    return None


class OpencodeServer:
    """A single running `opencode serve` process for one manifest."""

    def __init__(self, spec: ManifestSpec, opencode_bin: str = "opencode") -> None:
        self.spec = spec
        self.opencode_bin = opencode_bin
        self.base_url: str | None = None
        self.client: OpencodeClient | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._event_task: asyncio.Task | None = None
        self._log_handle: Any = None
        # Per-subscribed-root-session event queues.
        self._queues: dict[str, asyncio.Queue] = {}
        # child session id -> parent session id (from session.created).
        self._parent: dict[str, str] = {}
        self.last_used: float = time.monotonic()
        self._closed = False

    # --- lifecycle ---------------------------------------------------------

    async def start(self, *, readiness_timeout: float = 20.0) -> None:
        """Spawn the server, wait for readiness, and start the event reader."""
        port = _prealloc_port()
        env = build_server_env(self.spec.manifest_path, self.spec.agent_lib, self.spec.referenced_env_vars)
        log_dir = get_log_dir() / "opencode"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{self.spec.name}-{port}.log"
        self._log_handle = open(log_path, "w", encoding="utf-8")  # noqa: SIM115

        logger.info("Starting opencode server for %s on port %d (log: %s)", self.spec.name, port, log_path)
        self._process = await asyncio.create_subprocess_exec(
            self.opencode_bin,
            "serve",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
            "--print-logs",
            stdin=asyncio.subprocess.DEVNULL,
            stdout=self._log_handle,
            stderr=self._log_handle,
            env=env,
        )

        self.base_url = f"http://127.0.0.1:{port}"
        client = OpencodeClient(self.base_url)
        self.client = client

        # Poll readiness.
        deadline = time.monotonic() + readiness_timeout
        while time.monotonic() < deadline:
            if self._process.returncode is not None:
                raise RuntimeError(
                    f"opencode server for {self.spec.name} exited early (code {self._process.returncode}); "
                    f"see {log_path}"
                )
            if await client.ping():
                logger.info("opencode server for %s ready at %s", self.spec.name, self.base_url)
                self._event_task = asyncio.create_task(self._read_events())
                return
            await asyncio.sleep(0.25)
        await self.close()
        raise RuntimeError(f"opencode server for {self.spec.name} did not become ready within {readiness_timeout}s")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._event_task:
            self._event_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._event_task
        if self.client:
            await self.client.aclose()
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except TimeoutError:
                self._process.kill()
        if self._log_handle:
            self._log_handle.close()
        logger.info("Closed opencode server for %s", self.spec.name)

    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None and not self._closed

    def in_use(self) -> bool:
        return bool(self._queues)

    def touch(self) -> None:
        self.last_used = time.monotonic()

    # --- event demux -------------------------------------------------------

    def subscribe(self, root_session_id: str) -> asyncio.Queue:
        """Register a queue for a session (and its descendant sub-agent sessions)."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[root_session_id] = queue
        self.touch()
        return queue

    def unsubscribe(self, root_session_id: str) -> None:
        self._queues.pop(root_session_id, None)

    def _resolve_subscribed_root(self, session_id: str) -> str | None:
        """Walk the parent chain to find a subscribed ancestor (or self)."""
        seen: set[str] = set()
        sid: str | None = session_id
        while sid and sid not in seen:
            if sid in self._queues:
                return sid
            seen.add(sid)
            sid = self._parent.get(sid)
        return None

    async def _read_events(self) -> None:
        assert self.client is not None
        try:
            async for event in self.client.event_stream():
                self._route(event)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("opencode event stream for %s ended: %s", self.spec.name, e)

    def _route(self, event: dict[str, Any]) -> None:
        # Track hierarchy from session.created.
        if event.get("type") == "session.created":
            info = event.get("properties", {}).get("info", {})
            child, parent = info.get("id"), info.get("parentID")
            if isinstance(child, str) and isinstance(parent, str):
                self._parent[child] = parent
        sid = _event_session_id(event)
        if sid is None:
            return
        root = self._resolve_subscribed_root(sid)
        if root is not None:
            self._queues[root].put_nowait(event)
            self.touch()


class OpencodeServerRegistry:
    """Pool of OpencodeServer instances keyed by (manifest_name, content_hash)."""

    def __init__(self, opencode_bin: str = "opencode", max_servers: int = 8) -> None:
        self.opencode_bin = opencode_bin
        self.max_servers = max_servers
        self._servers: dict[tuple[str, str], OpencodeServer] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, spec: ManifestSpec) -> OpencodeServer:
        async with self._lock:
            server = self._servers.get(spec.key)
            if server is not None and server.is_alive():
                server.touch()
                return server
            # Retire a stale/dead entry under the same name (e.g. manifest edited).
            for key in [k for k in self._servers if k[0] == spec.name]:
                old = self._servers.pop(key)
                if not old.in_use():
                    await old.close()
            await self._evict_if_over_cap()
            server = OpencodeServer(spec, opencode_bin=self.opencode_bin)
            await server.start()
            self._servers[spec.key] = server
            return server

    async def _evict_if_over_cap(self) -> None:
        """Evict the LRU idle server if at/over the concurrency cap."""
        while len(self._servers) >= self.max_servers:
            idle = [(k, s) for k, s in self._servers.items() if not s.in_use()]
            if not idle:
                logger.warning("opencode server pool at cap (%d) with all servers busy", self.max_servers)
                return
            key, server = min(idle, key=lambda kv: kv[1].last_used)
            self._servers.pop(key)
            await server.close()
            logger.info("Evicted LRU idle opencode server %s", key[0])

    async def cleanup_idle(self, idle_secs: float = 1800.0) -> int:
        now = time.monotonic()
        async with self._lock:
            to_close = [key for key, s in self._servers.items() if not s.in_use() and (now - s.last_used) > idle_secs]
            for key in to_close:
                await self._servers.pop(key).close()
        if to_close:
            logger.info("Reaped %d idle opencode servers", len(to_close))
        return len(to_close)

    async def close_all(self) -> None:
        async with self._lock:
            for server in list(self._servers.values()):
                await server.close()
            self._servers.clear()

    def active_count(self) -> int:
        return len(self._servers)
