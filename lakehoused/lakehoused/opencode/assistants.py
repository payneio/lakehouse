"""LakehouseOpencodeManager: the assistant catalog over the manifest repo.

An "assistant" is one opencode config manifest
(`<repo>/manifests/<name>.json`) that shares the repo's `<repo>/_library/`.
Discovery is plain file scanning; there is no Foundation registry, includes chain,
or git resolution. `resolve()` produces the ManifestSpec the server pool boots
from plus the default agent/model for a turn.

Contract:
- Inputs: assistant repo path (opencode_assistants_path), manifest name
- Outputs: ManifestSpec + agent/model/description; catalog list/details; file CRUD
- Side effects: reads/writes manifest JSON files
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..storage.paths import get_opencode_assistants_dir
from .server_manager import ManifestSpec
from .server_manager import extract_env_var_names

logger = logging.getLogger(__name__)


@dataclass
class AssistantInfo:
    """Summary info about a discovered assistant manifest."""

    name: str
    path: Path
    source: str  # always "user" (manifests are user-editable files)


@dataclass
class ResolvedManifest:
    """Everything session creation needs for an assistant."""

    name: str
    spec: ManifestSpec
    default_agent: str | None
    model: str | None
    description: str | None


class LakehouseOpencodeManager:
    """Discovers and resolves opencode assistant manifests."""

    def __init__(self, assistants_path: str | Path | None = None) -> None:
        self._root = Path(assistants_path).expanduser().resolve() if assistants_path else get_opencode_assistants_dir()
        self._manifests_dir = self._root / "manifests"
        self._agent_lib = self._root / "_library"

    @property
    def root(self) -> Path:
        return self._root

    @property
    def agent_lib(self) -> Path:
        return self._agent_lib

    @property
    def manifests_dir(self) -> Path:
        return self._manifests_dir

    def _manifest_path(self, name: str) -> Path:
        return self._manifests_dir / f"{name}.json"

    # --- discovery ---------------------------------------------------------

    def list_manifests(self) -> list[AssistantInfo]:
        if not self._manifests_dir.exists():
            logger.warning("opencode manifests dir does not exist: %s", self._manifests_dir)
            return []
        out: list[AssistantInfo] = []
        for path in sorted(self._manifests_dir.glob("*.json")):
            out.append(AssistantInfo(name=path.stem, path=path, source="user"))
        return out

    def list_available_assistants(self) -> list[str]:
        return [a.name for a in self.list_manifests()]

    def list_assistants(self) -> list[AssistantInfo]:
        return self.list_manifests()

    def get_assistant_info(self, name: str) -> AssistantInfo | None:
        path = self._manifest_path(name)
        if path.exists():
            return AssistantInfo(name=name, path=path, source="user")
        return None

    # --- loading & resolution ---------------------------------------------

    def _load_manifest(self, name: str) -> tuple[str, dict[str, Any]]:
        path = self._manifest_path(name)
        if not path.exists():
            raise FileNotFoundError(f"Assistant manifest not found: {name}")
        text = path.read_text(encoding="utf-8")
        return text, json.loads(text)

    def manifest_spec(self, name: str) -> ManifestSpec:
        text, _ = self._load_manifest(name)
        return ManifestSpec(
            name=name,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
            manifest_path=self._manifest_path(name),
            agent_lib=self._agent_lib,
            referenced_env_vars=extract_env_var_names(text),
        )

    def resolve(self, name: str) -> ResolvedManifest:
        """Resolve an assistant to a ManifestSpec + default agent/model/description."""
        text, data = self._load_manifest(name)
        spec = ManifestSpec(
            name=name,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:12],
            manifest_path=self._manifest_path(name),
            agent_lib=self._agent_lib,
            referenced_env_vars=extract_env_var_names(text),
        )
        default_agent = data.get("default_agent")
        model = data.get("model")
        description = self._describe(data, default_agent)
        return ResolvedManifest(name=name, spec=spec, default_agent=default_agent, model=model, description=description)

    @staticmethod
    def _describe(data: dict[str, Any], default_agent: str | None) -> str | None:
        if isinstance(data.get("description"), str):
            return data["description"]
        agents = data.get("agent")
        if isinstance(agents, dict) and default_agent and isinstance(agents.get(default_agent), dict):
            desc = agents[default_agent].get("description")
            if isinstance(desc, str):
                return desc
        return None

    # --- catalog details (assistants router) -------------------------------

    async def get_assistant_details(self, name: str) -> dict[str, Any]:
        _, data = self._load_manifest(name)
        agents = data.get("agent") or {}
        mcp = data.get("mcp") or {}
        plugins = data.get("plugin") or []
        return {
            "name": name,
            "version": "1.0.0",
            "description": self._describe(data, data.get("default_agent")),
            "source": "user",
            "path": str(self._manifest_path(name)),
            "provider_count": len(data.get("provider") or {}),
            "tool_count": len(mcp),
            "hook_count": len(plugins),
            "agent_count": len(agents),
            "includes": [],
            "session": None,
            "providers": [{"module": p} for p in (data.get("provider") or {})],
            "tools": [{"module": m} for m in mcp],
            "hooks": [],
            "agents": [{"module": a} for a in agents],
            "context": {},
            "instruction": None,
            "default_agent": data.get("default_agent"),
            "model": data.get("model"),
        }

    async def get_resolved_assistant(self, name: str) -> dict[str, Any]:
        details = await self.get_assistant_details(name)

        # ResolvedModuleRef requires `defined_in`; assistants have no includes
        # chain, so every module is "defined in" the assistant itself.
        def refs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [{**item, "defined_in": name} for item in items]

        return {
            "name": name,
            "source": "user",
            "git_url": None,
            "includes_chain": [name],
            "includes_tree": {"name": name, "includes": []},
            "session": None,
            "providers": refs(details["providers"]),
            "tools": refs(details["tools"]),
            "hooks": refs(details["hooks"]),
            "agents": refs(details["agents"]),
            "instruction": None,
        }

    async def get_assistant_source(self, name: str) -> tuple[str, str, str]:
        text, _ = self._load_manifest(name)
        return text, str(self._manifest_path(name)), "json"

    def is_user_assistant(self, name: str) -> bool:
        return self._manifest_path(name).exists()

    # --- CRUD (plain file ops on the manifest repo) ------------------------

    async def create_assistant(
        self, name: str, base_assistant: str | None = None, description: str | None = None
    ) -> AssistantInfo:
        path = self._manifest_path(name)
        if path.exists():
            raise ValueError(f"Assistant already exists: {name}")
        self._manifests_dir.mkdir(parents=True, exist_ok=True)
        if base_assistant:
            _, data = self._load_manifest(base_assistant)
        else:
            data = {"$schema": "https://opencode.ai/config.json", "agent": {}}
        if description:
            data["description"] = description
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Created assistant %s", name)
        return AssistantInfo(name=name, path=path, source="user")

    async def copy_assistant(self, source_name: str, new_name: str) -> AssistantInfo:
        src = self._manifest_path(source_name)
        dst = self._manifest_path(new_name)
        if not src.exists():
            raise ValueError(f"Source assistant not found: {source_name}")
        if dst.exists():
            raise ValueError(f"Assistant already exists: {new_name}")
        shutil.copy2(src, dst)
        logger.info("Copied assistant %s -> %s", source_name, new_name)
        return AssistantInfo(name=new_name, path=dst, source="user")

    def update_assistant(self, name: str, content: str) -> None:
        path = self._manifest_path(name)
        if not path.exists():
            raise ValueError(f"Assistant not found: {name}")
        # Validate JSON before writing.
        json.loads(content)
        path.write_text(content, encoding="utf-8")
        logger.info("Updated assistant %s", name)

    def rename_assistant(self, old_name: str, new_name: str) -> AssistantInfo:
        src = self._manifest_path(old_name)
        dst = self._manifest_path(new_name)
        if not src.exists():
            raise ValueError(f"Assistant not found: {old_name}")
        if dst.exists():
            raise ValueError(f"Assistant already exists: {new_name}")
        src.rename(dst)
        logger.info("Renamed assistant %s -> %s", old_name, new_name)
        return AssistantInfo(name=new_name, path=dst, source="user")

    def delete_assistant(self, name: str) -> None:
        path = self._manifest_path(name)
        if not path.exists():
            raise ValueError(f"Assistant not found: {name}")
        path.unlink()
        logger.info("Deleted assistant %s", name)
