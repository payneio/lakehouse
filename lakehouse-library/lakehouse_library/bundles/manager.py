"""Lakehouse bundle manager - integrates Foundation bundles with Lakehouse sessions.

Wraps Foundation's BundleRegistry to provide:
- Well-known bundle paths at ~/.lakehoused/bundles/
- Runtime config injection for sessions
- Simplified API for session creation
- Bundle source detection (user vs system)
- Bundle CRUD operations
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amplifier_foundation import Bundle
from amplifier_foundation import BundleRegistry

from lakehouse_library.storage.paths import get_bundles_dir
from lakehouse_library.storage.paths import get_home_dir

logger = logging.getLogger(__name__)


@dataclass
class BundleInfo:
    """Information about a discovered bundle."""

    name: str
    path: Path
    source: str  # 'user' or 'system'
    uri: str


class LakehouseBundleManager:
    """Manages bundle loading and mount plan generation for Lakehouse.

    Wraps Foundation's BundleRegistry to:
    1. Use ~/.lakehoused/bundles/ as well-known bundle location
    2. Convert bundles to mount plans with runtime config injection
    3. Provide simplified API for session creation
    4. Track bundle source (user vs system) for UI

    Example:
        manager = LakehouseBundleManager()
        mount_plan = await manager.generate_mount_plan(
            bundle_ref="software-developer",
            session_id="sess-123",
            project_path="/data/projects/myproject",
        )
    """

    def __init__(
        self,
        home_dir: Path | None = None,
        registry_bundles: dict[str, str] | None = None,
    ) -> None:
        """Initialize bundle manager.

        Args:
            home_dir: Base directory for Lakehouse data. Defaults to ~/.lakehoused.
                      Bundles are loaded from {home_dir}/bundles/.
            registry_bundles: Bundle name->URI mappings from BUNDLES.txt.
                              These are git+ URIs that Foundation will resolve
                              via git cloning. Registered FIRST before local discovery.
        """
        self._home_dir = home_dir or get_home_dir()
        # All local bundles are in share/bundles (user-editable)
        # Registry bundles (git+ URIs) are cached separately by Foundation
        if home_dir:
            # Test isolation: derive from provided home_dir
            self._bundles_dir = home_dir / "share" / "bundles"
        else:
            # Production: use paths module
            self._bundles_dir = get_bundles_dir()

        # Initialize Foundation's BundleRegistry with our home directory
        # Foundation uses {home}/cache for remote bundle caching
        self._registry = BundleRegistry(home=self._home_dir)

        # Track bundle info (name -> BundleInfo) for source detection
        self._bundle_info: dict[str, BundleInfo] = {}

        # Store registry bundles to avoid overwriting during local discovery
        self._registry_bundles = registry_bundles or {}

        # Register bundles from BUNDLES.txt (git+ URIs) FIRST
        # Foundation handles git cloning/caching, preserving full repo structure
        # for namespace:path resolution (e.g., foundation:behaviors/sessions)
        if registry_bundles:
            self._registry.register(registry_bundles)
            # Track registry bundles in _bundle_info for list_bundles_with_info()
            for name, uri in registry_bundles.items():
                self._bundle_info[name] = BundleInfo(
                    name=name,
                    path=Path(uri),  # Store URI as path for display
                    source="registry",
                    uri=uri,
                )
            logger.info(f"Registered {len(registry_bundles)} bundles from BUNDLES.txt")

        # Then discover local bundles (skip names already in registry_bundles)
        self._discover_local_bundles()

    @property
    def home_dir(self) -> Path:
        """Base directory for Lakehouse data."""
        return self._home_dir

    @property
    def bundles_dir(self) -> Path:
        """Directory containing local bundles."""
        return self._bundles_dir

    @property
    def registry(self) -> BundleRegistry:
        """Underlying Foundation BundleRegistry."""
        return self._registry

    def _discover_local_bundles(self) -> None:
        """Discover and register bundles in the bundles directory.

        All local bundles are in share/bundles/ and are user-editable.
        Registry bundles (git+ URIs) are cached separately by Foundation.

        Supports multiple bundle formats:
        - Single .md files (e.g., basic.md) - name derived from filename
        - Directories containing bundle.yaml or bundle.md - name from directory

        Registers each as a local file:// URI.
        """
        discovered: dict[str, str] = {}

        if not self._bundles_dir.exists():
            logger.debug(f"Bundles directory does not exist: {self._bundles_dir}")
            return

        # All local bundles are "user" bundles (editable)
        self._discover_bundles_in_dir(self._bundles_dir, discovered, source_type="user")

        if discovered:
            self._registry.register(discovered)
            logger.info(f"Discovered {len(discovered)} local bundles")

    def _discover_bundles_in_dir(
        self, bundles_dir: Path, discovered: dict[str, str], prefix: str = "", source_type: str = "system"
    ) -> None:
        """Discover bundles in a directory, recursively scanning subdirectories.

        Args:
            bundles_dir: Directory to scan.
            discovered: Dict to update with discovered bundles (name -> URI).
            prefix: Prefix for nested bundles (e.g., "foundation/" for foundation/base.md).
            source_type: Bundle source type ('user' or 'system').
        """
        for item in bundles_dir.iterdir():
            if item.is_file() and item.suffix in [".md", ".yaml"]:
                # Single bundle file (e.g., basic.md, amplifier-dev.yaml)
                bundle_name = prefix + item.stem  # Remove extension
                bundle_uri = f"file://{item.resolve()}"

                # Don't overwrite if:
                # - Already discovered (user bundles take priority over share/)
                # - Already in registry_bundles (git+ URIs from BUNDLES.txt)
                if bundle_name not in discovered and bundle_name not in self._registry_bundles:
                    discovered[bundle_name] = bundle_uri
                    self._bundle_info[bundle_name] = BundleInfo(
                        name=bundle_name,
                        path=item.resolve(),
                        source=source_type,
                        uri=bundle_uri,
                    )
                    logger.debug(f"Discovered bundle file: {bundle_name} -> {bundle_uri} ({source_type})")

            elif item.is_dir():
                # Check if it's a bundle directory (contains bundle.md or bundle.yaml)
                bundle_md = item / "bundle.md"
                bundle_yaml = item / "bundle.yaml"

                if bundle_md.exists() or bundle_yaml.exists():
                    # Directory-style bundle
                    bundle_name = prefix + item.name
                    bundle_uri = f"file://{item.resolve()}"
                    bundle_file = bundle_md if bundle_md.exists() else bundle_yaml

                    # Don't overwrite if already discovered or in registry_bundles
                    if bundle_name not in discovered and bundle_name not in self._registry_bundles:
                        discovered[bundle_name] = bundle_uri
                        self._bundle_info[bundle_name] = BundleInfo(
                            name=bundle_name,
                            path=bundle_file,
                            source=source_type,
                            uri=bundle_uri,
                        )
                        logger.debug(f"Discovered bundle dir: {bundle_name} -> {bundle_uri} ({source_type})")
                else:
                    # Recurse into subdirectory (e.g., foundation/)
                    self._discover_bundles_in_dir(
                        item, discovered, prefix=prefix + item.name + "/", source_type=source_type
                    )

    async def load_bundle(self, bundle_ref: str) -> Bundle:
        """Load a bundle by name or URI.

        Args:
            bundle_ref: Bundle name (from registry) or URI (git+, file://, etc.)

        Returns:
            Loaded Bundle instance.

        Raises:
            BundleNotFoundError: If bundle cannot be found.
            BundleLoadError: If bundle fails to load.
        """
        # registry.load() returns Bundle for single name/URI, dict for None
        # Since we always pass a string, we always get a Bundle back
        result = await self._registry.load(bundle_ref)
        assert isinstance(result, Bundle)  # Type narrowing for type checker
        return result

    def bundle_to_mount_plan(self, bundle: Bundle) -> dict[str, Any]:
        """Convert a Bundle to a mount plan dict.

        Args:
            bundle: Bundle to convert.

        Returns:
            Mount plan dict suitable for AmplifierSession.
        """
        mount_plan = bundle.to_mount_plan()

        # Include composed instruction (from markdown body) for context message generation
        # This is the primary instruction content that should be injected into LLM context
        if bundle.instruction:
            mount_plan["instruction"] = bundle.instruction

        # Include source_base_paths for @namespace:path @mention resolution
        # This maps bundle namespaces (e.g., "foundation") to their base paths
        # enabling @foundation:context/file.md to resolve correctly
        if bundle.source_base_paths:
            mount_plan["source_base_paths"] = {ns: str(path) for ns, path in bundle.source_base_paths.items()}

        return mount_plan

    async def generate_mount_plan(
        self,
        bundle_ref: str,
        session_id: str,
        project_path: str,
        *,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Generate a complete mount plan with runtime config injected.

        This is the main entry point for session creation. It:
        1. Loads the bundle from registry or URI
        2. Converts to mount plan dict
        3. Injects runtime config (working_dir, allowed_write_paths, etc.)

        Args:
            bundle_ref: Bundle name or URI.
            session_id: Session ID for logging and state.
            project_path: Absolute path to the project directory.
            api_key: Optional API key for providers.

        Returns:
            Mount plan dict ready for ExecutionRunner/AmplifierSession.
        """
        # Load bundle
        bundle = await self.load_bundle(bundle_ref)

        # Convert to mount plan
        mount_plan = self.bundle_to_mount_plan(bundle)

        # Inject runtime configuration
        mount_plan = self._inject_runtime_config(
            mount_plan=mount_plan,
            session_id=session_id,
            project_path=project_path,
            api_key=api_key,
        )

        return mount_plan

    def _inject_runtime_config(
        self,
        mount_plan: dict[str, Any],
        session_id: str,
        project_path: str,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Inject runtime configuration into mount plan.

        Adds session-specific config that can't be known at bundle authoring time:
        - working_dir for tools
        - allowed_write_paths for filesystem security
        - session_log_template for logging
        - api_key for providers

        Args:
            mount_plan: Mount plan dict to modify.
            session_id: Session ID.
            project_path: Absolute path to project directory.
            api_key: Optional API key.

        Returns:
            Modified mount plan dict.
        """
        # Inject into tools
        if "tools" in mount_plan:
            for tool in mount_plan["tools"]:
                if "config" not in tool:
                    tool["config"] = {}

                # Set working_dir if not already set
                if "working_dir" not in tool["config"]:
                    tool["config"]["working_dir"] = project_path

                # For filesystem tools, inject allowed_write_paths
                tool_module = tool.get("module", "") or tool.get("id", "")
                tool_source = tool.get("source", "")
                is_filesystem_tool = "tool-filesystem" in tool_module or "filesystem" in tool_source

                if is_filesystem_tool and "allowed_write_paths" not in tool["config"]:
                    tool["config"]["allowed_write_paths"] = [project_path]

        # Inject into hooks
        if "hooks" in mount_plan:
            for hook in mount_plan["hooks"]:
                if "config" not in hook:
                    hook["config"] = {}

                # Set session_log_template for logging hooks
                # Always override with lakehouse-specific path (bundles may have different paths)
                hook_module = hook.get("module", "") or hook.get("id", "")
                hook_source = hook.get("source", "")
                is_logging_hook = "logging" in hook_module or "logging" in hook_source

                if is_logging_hook:
                    # Use {session_id} placeholder - Foundation replaces at runtime
                    hook["config"]["session_log_template"] = str(
                        self._home_dir / "state" / "sessions" / "{session_id}" / "events.jsonl"
                    )

        # Inject config into providers
        if "providers" in mount_plan:
            for provider in mount_plan["providers"]:
                if "config" not in provider:
                    provider["config"] = {}

                # Inject API key if provided
                if api_key and "api_key" not in provider["config"]:
                    provider["config"]["api_key"] = api_key

                # Enable debug logging for raw request/response events
                # This allows hooks-logging to capture llm:request:raw and llm:response:raw
                if "debug" not in provider["config"]:
                    provider["config"]["debug"] = True
                if "raw_debug" not in provider["config"]:
                    provider["config"]["raw_debug"] = True

        return mount_plan

    def list_available_bundles(self) -> list[str]:
        """List all available bundle names.

        Returns:
            Sorted list of registered bundle names.
        """
        return self._registry.list_registered()

    def get_bundle_info(self, name: str) -> BundleInfo | None:
        """Get bundle info by name.

        Args:
            name: Bundle name.

        Returns:
            BundleInfo if found, None otherwise.
        """
        return self._bundle_info.get(name)

    def list_bundles_with_info(self) -> list[BundleInfo]:
        """List all bundles with their info.

        Returns:
            List of BundleInfo for all discovered bundles.
        """
        return list(self._bundle_info.values())

    async def get_bundle_details(self, name: str) -> dict[str, Any]:
        """Get detailed bundle information.

        Args:
            name: Bundle name.

        Returns:
            Dict with bundle details including metadata, modules, and stats.

        Raises:
            ValueError: If bundle not found.
        """
        info = self._bundle_info.get(name)
        # For registry bundles, info might not exist yet - check if registered
        if not info:
            registered = self._registry.list_registered()
            if name not in registered:
                raise ValueError(f"Bundle not found: {name}")
            # Create temporary info for registry bundle
            info = BundleInfo(
                name=name,
                path=Path(name),  # Placeholder
                source="registry",
                uri=name,
            )

        # Load the bundle to get full details
        bundle = await self.load_bundle(name)

        # Extract module lists from bundle
        providers = bundle.providers or []
        tools = bundle.tools or []
        hooks = bundle.hooks or []

        # Build session config
        session_config = None
        if bundle.session:
            session_config = {
                "orchestrator": bundle.session.get("orchestrator"),
                "context": bundle.session.get("context"),
            }

        # Build agents list as module refs
        agents_list = []
        for agent_name, agent_config in (bundle.agents or {}).items():
            agents_list.append(
                {
                    "module": agent_name,
                    "source": agent_config.get("source"),
                    "config": agent_config.get("config"),
                }
            )

        return {
            "name": bundle.name,
            "version": bundle.version,
            "description": bundle.description or None,
            "source": info.source,
            "path": str(info.path),
            "provider_count": len(providers),
            "tool_count": len(tools),
            "hook_count": len(hooks),
            "agent_count": len(agents_list),
            "includes": bundle.includes or [],
            "session": session_config,
            "providers": providers,
            "tools": tools,
            "hooks": hooks,
            "agents": agents_list,
            "context": {k: str(v) for k, v in (bundle.context or {}).items()},
            "instruction": bundle.instruction,
        }

    async def get_resolved_bundle(self, name: str) -> dict[str, Any]:
        """Get a flattened/resolved view of a bundle with source tracking.

        This resolves all includes and tracks which bundle contributed
        each component. Used for the UI to show what will actually run.

        Args:
            name: Bundle name.

        Returns:
            Dict with resolved bundle including includes_chain and source tracking.

        Raises:
            ValueError: If bundle not found.
        """
        info = self._bundle_info.get(name)
        if not info:
            raise ValueError(f"Bundle not found: {name}")

        # Build includes chain by loading bundles WITHOUT includes
        # This caches bundles without includes composed - we need this for the raw includes list
        includes_chain = await self._build_includes_chain(name)

        # Build includes tree for UI display of nesting structure
        includes_tree = await self._build_includes_tree(name)

        # Track contributions: module_id -> (bundle_name, config, source)
        def track_modules(module_list: list[dict], bundle_name: str, contributions: dict) -> None:
            """Track which bundle contributed each module."""
            for mod in module_list:
                mod_id = mod.get("module") or mod.get("id", "")
                if mod_id:
                    if mod_id not in contributions:
                        contributions[mod_id] = {
                            "defined_in": bundle_name,
                            "config": mod.get("config"),
                            "source": mod.get("source", ""),
                        }
                    else:
                        # Check if config changed (override)
                        prev = contributions[mod_id]
                        new_config = mod.get("config")
                        if new_config != prev.get("config"):
                            contributions[mod_id] = {
                                "defined_in": prev["defined_in"],
                                "overridden": True,
                                "override_in": bundle_name,
                                "original_config": prev.get("config"),
                                "config": new_config,
                                "source": mod.get("source", prev.get("source", "")),
                            }

        # Process each bundle in chain order to track where components are FIRST defined
        # We compose manually to track sources while building the final bundle
        provider_contributions: dict[str, Any] = {}
        tool_contributions: dict[str, Any] = {}
        hook_contributions: dict[str, Any] = {}
        agent_contributions: dict[str, Any] = {}

        # Load each bundle in chain individually to get direct declarations
        # Foundation's _load_single(auto_include=False) returns a Bundle with only its
        # direct declarations (no includes composed), which is exactly what we need
        for bundle_ref in includes_chain:
            # Use friendly name for display in defined_in fields
            friendly_name = self._resolve_to_friendly_name(bundle_ref)
            try:
                bundle = await self._registry._load_single(
                    bundle_ref,
                    auto_register=True,
                    auto_include=False,  # Get direct declarations only
                )

                # Track direct declarations from this bundle using friendly name
                track_modules(bundle.providers or [], friendly_name, provider_contributions)
                track_modules(bundle.tools or [], friendly_name, tool_contributions)
                track_modules(bundle.hooks or [], friendly_name, hook_contributions)

                # Track agents
                for agent_name, agent_config in (bundle.agents or {}).items():
                    if agent_name not in agent_contributions:
                        agent_contributions[agent_name] = {
                            "defined_in": friendly_name,
                            "config": agent_config,
                        }
                    else:
                        prev = agent_contributions[agent_name]
                        if agent_config != prev.get("config"):
                            agent_contributions[agent_name] = {
                                "defined_in": prev["defined_in"],
                                "overridden": True,
                                "override_in": friendly_name,
                                "original_config": prev.get("config"),
                                "config": agent_config,
                            }

            except Exception as e:
                logger.warning(f"Failed to load bundle {bundle_ref} for source tracking: {e}")

        # IMPORTANT: Clear the cache before loading the final composed bundle.
        # The previous _load_single calls with auto_include=False cached bundles without
        # includes composed. We need to clear that cache so load_bundle() gets the fully
        # composed bundle with all includes merged.
        self._registry._loaded_bundles.clear()
        final_bundle = await self.load_bundle(name)

        # Build resolved module lists by enriching final_bundle components with source tracking
        # We iterate over final_bundle to get ALL components (including from remote bundles),
        # then add source tracking from our contributions dict
        def build_resolved_modules(module_list: list[dict], contributions: dict) -> list[dict]:
            result = []
            for mod in module_list:
                mod_id = mod.get("module") or mod.get("id", "")
                contrib = contributions.get(mod_id, {})
                result.append(
                    {
                        "module": mod_id,
                        "source": mod.get("source", ""),
                        "config": mod.get("config"),
                        "defined_in": contrib.get("defined_in", name),  # Default to current bundle if not tracked
                        "overridden": contrib.get("overridden", False),
                        "override_in": contrib.get("override_in"),
                        "original_config": contrib.get("original_config"),
                    }
                )
            return result

        # Build resolved agents list
        resolved_agents = []
        for agent_name, contrib in agent_contributions.items():
            agent_config = contrib.get("config", {})
            resolved_agents.append(
                {
                    "module": agent_name,
                    "source": agent_config.get("source") if isinstance(agent_config, dict) else None,
                    "config": agent_config.get("config") if isinstance(agent_config, dict) else None,
                    "defined_in": contrib.get("defined_in", name),
                    "overridden": contrib.get("overridden", False),
                    "override_in": contrib.get("override_in"),
                    "original_config": contrib.get("original_config"),
                }
            )

        # Build session config with source tracking
        session_config = None
        if final_bundle.session:
            orch = final_bundle.session.get("orchestrator")
            ctx = final_bundle.session.get("context")
            session_config = {
                "orchestrator": {
                    "module": orch.get("module") if orch else None,
                    "source": orch.get("source") if orch else None,
                    "config": orch.get("config") if orch else None,
                    "defined_in": name,  # Session is always from final bundle
                    "overridden": False,
                }
                if orch
                else None,
                "context": {
                    "module": ctx.get("module") if ctx else None,
                    "source": ctx.get("source") if ctx else None,
                    "config": ctx.get("config") if ctx else None,
                    "defined_in": name,
                    "overridden": False,
                }
                if ctx
                else None,
            }

        # Convert includes_chain to friendly names for display
        friendly_chain = [self._resolve_to_friendly_name(ref) for ref in includes_chain]

        return {
            "name": final_bundle.name,
            "source": info.source,
            "includes_chain": friendly_chain,
            "includes_tree": includes_tree,
            "session": session_config,
            "providers": build_resolved_modules(final_bundle.providers or [], provider_contributions),
            "tools": build_resolved_modules(final_bundle.tools or [], tool_contributions),
            "hooks": build_resolved_modules(final_bundle.hooks or [], hook_contributions),
            "agents": resolved_agents,
            "instruction": final_bundle.instruction,
        }

    async def _build_includes_tree(self, name: str, seen: set[str] | None = None) -> dict[str, Any]:
        """Build the includes tree for a bundle showing nesting structure.

        Args:
            name: Bundle name.
            seen: Set of already-seen bundle names (for cycle detection).

        Returns:
            Dict with 'name' and 'includes' (list of child trees).
        """
        if seen is None:
            seen = set()

        friendly_name = self._resolve_to_friendly_name(name)

        if name in seen:
            return {"name": friendly_name, "includes": []}  # Cycle detected
        seen.add(name)

        # Load bundle WITHOUT includes to get its direct includes list
        try:
            bundle = await self._registry._load_single(
                name,
                auto_register=True,
                auto_include=False,
            )
        except Exception as e:
            logger.warning(f"Failed to load bundle {name} for includes tree: {e}")
            return {"name": friendly_name, "includes": []}

        children = []
        for include in bundle.includes or []:
            include_source = self._parse_include(include)
            if include_source:
                child_tree = await self._build_includes_tree(include_source, seen.copy())
                children.append(child_tree)

        return {"name": friendly_name, "includes": children}

    async def _build_includes_chain(self, name: str, seen: set[str] | None = None) -> list[str]:
        """Build the full includes chain for a bundle.

        Args:
            name: Bundle name.
            seen: Set of already-seen bundle names (for cycle detection).

        Returns:
            List of bundle names in order (dependencies first, target last).
        """
        if seen is None:
            seen = set()

        if name in seen:
            return []  # Cycle detected
        seen.add(name)

        # Load bundle WITHOUT includes to get its direct includes list
        try:
            bundle = await self._registry._load_single(
                name,
                auto_register=True,
                auto_include=False,  # Don't compose, just get direct declarations
            )
        except Exception as e:
            logger.warning(f"Failed to load bundle {name} for includes chain: {e}")
            return [name]

        chain = []

        # Process includes from the loaded bundle
        for include in bundle.includes or []:
            include_source = self._parse_include(include)
            if include_source:
                sub_chain = await self._build_includes_chain(include_source, seen)
                for b in sub_chain:
                    if b not in chain:
                        chain.append(b)

        if name not in chain:
            chain.append(name)

        return chain

    def _parse_include(self, include: str | dict) -> str | None:
        """Parse include directive to get bundle name or URI.

        Args:
            include: Include directive (string or dict with 'bundle' key).

        Returns:
            Bundle name/URI or None if couldn't parse.
        """
        if isinstance(include, str):
            return include
        if isinstance(include, dict):
            bundle_ref = include.get("bundle")
            if bundle_ref:
                return str(bundle_ref)
        return None

    def _resolve_to_friendly_name(self, bundle_ref: str) -> str:
        """Resolve a bundle reference (name or URI) to a friendly display name.

        For URIs like 'git+https://github.com/.../something.yaml#subdirectory=path/to/bundle.md',
        this extracts a friendly name. For registered names, returns as-is.

        Args:
            bundle_ref: Bundle name or URI.

        Returns:
            Friendly name for display.
        """
        # Check if it's already a registered name (not a URI)
        if not bundle_ref.startswith(("git+", "file://", "http://", "https://")):
            return bundle_ref

        # Check if this URI is in our registry_bundles (reverse lookup)
        for name, uri in self._registry_bundles.items():
            if uri == bundle_ref:
                return name

        # Check bundle_info for URI matches
        for info in self._bundle_info.values():
            if info.uri == bundle_ref:
                return info.name

        # Extract from URI - try to get a meaningful name
        # Format: git+https://github.com/org/repo@branch#subdirectory=path/to/bundle.md
        if "#subdirectory=" in bundle_ref:
            # Extract from subdirectory fragment
            fragment = bundle_ref.split("#subdirectory=", 1)[1]
            # Get filename without extension
            name = fragment.rsplit("/", 1)[-1]  # Last path component
            if name.endswith((".md", ".yaml", ".yml")):
                name = name.rsplit(".", 1)[0]
            return name

        # Try to extract from namespace:path format
        if ":" in bundle_ref and not bundle_ref.startswith(("git+", "file:", "http:", "https:")):
            # Format: namespace:path/to/bundle
            path_part = bundle_ref.split(":", 1)[1]
            name = path_part.rsplit("/", 1)[-1]
            if name.endswith((".md", ".yaml", ".yml")):
                name = name.rsplit(".", 1)[0]
            return name

        # Fallback: extract repo name from git URL
        # git+https://github.com/org/repo@branch
        if "github.com/" in bundle_ref:
            try:
                # Extract org/repo part
                parts = bundle_ref.split("github.com/", 1)[1]
                if "@" in parts:
                    parts = parts.split("@", 1)[0]
                if "/" in parts:
                    repo = parts.split("/")[1]
                    return repo
            except (IndexError, ValueError):
                pass

        # Last resort: return the URI (truncated for readability)
        if len(bundle_ref) > 50:
            return f"...{bundle_ref[-47:]}"
        return bundle_ref

    async def get_bundle_source_content(self, name: str) -> tuple[str, str, str]:
        """Get the raw source content of a bundle file.

        Args:
            name: Bundle name.

        Returns:
            Tuple of (content, path, format) where format is 'md', 'yaml', or 'directory'.

        Raises:
            ValueError: If bundle not found.
        """
        info = self._bundle_info.get(name)
        if not info:
            raise ValueError(f"Bundle not found: {name}")

        # For registry bundles (git+ URIs), we need to resolve the cached path
        if info.source == "registry":
            # Load the bundle to get its cached location
            # Foundation caches git+ bundles to disk and sets base_path
            try:
                bundle = await self._registry._load_single(
                    name,
                    auto_register=False,
                    auto_include=False,
                )
                # For registry bundles with subdirectory=, we need the repo root
                # source_base_paths[bundle.name] contains the repo root
                # base_path is just the parent dir of the file, not the repo root
                repo_root = bundle.source_base_paths.get(bundle.name) if bundle.source_base_paths else None

                if not repo_root and not bundle.base_path:
                    raise ValueError(f"Bundle {name} has no base_path after loading")

                uri = info.uri
                path = None

                # Check if URI has a fragment with subdirectory=
                if "#" in uri and "subdirectory=" in uri.split("#", 1)[1]:
                    fragment = uri.split("#", 1)[1]
                    if fragment.startswith("subdirectory="):
                        fragment = fragment.split("=", 1)[1]

                    # Use repo root from source_base_paths, not base_path
                    # source_base_paths[name] = repo root (set by Registry)
                    # base_path = parent of bundle file (NOT repo root for subdirectory bundles)
                    if repo_root:
                        path = repo_root / fragment
                    elif bundle.base_path:
                        # Fallback: no source_base_paths, try base_path
                        path = bundle.base_path / fragment
                else:
                    # No subdirectory fragment - base_path is the bundle directory
                    path = bundle.base_path

                if path is None:
                    raise ValueError(f"Could not determine path for bundle {name}")
            except Exception as e:
                raise ValueError(f"Failed to load registry bundle {name}: {e}")
        else:
            path = info.path

        # Determine format and read content
        if path.is_dir():
            # Directory bundle - look for bundle.md or bundle.yaml
            bundle_md = path / "bundle.md"
            bundle_yaml = path / "bundle.yaml"
            if bundle_md.exists():
                content = bundle_md.read_text()
                file_format = "md"
                actual_path = bundle_md
            elif bundle_yaml.exists():
                content = bundle_yaml.read_text()
                file_format = "yaml"
                actual_path = bundle_yaml
            else:
                raise ValueError(f"Bundle directory missing bundle.md or bundle.yaml: {path}")
        else:
            content = path.read_text()
            file_format = "md" if path.suffix == ".md" else "yaml"
            actual_path = path

        return content, str(actual_path), file_format

    def is_user_bundle(self, name: str) -> bool:
        """Check if a bundle is a user bundle (editable).

        Args:
            name: Bundle name.

        Returns:
            True if user bundle, False if system bundle or not found.
        """
        info = self._bundle_info.get(name)
        return info is not None and info.source == "user"

    async def copy_bundle(self, source_name: str, new_name: str) -> BundleInfo:
        """Copy a bundle to user bundles directory.

        All bundles are directories. This copies:
        - Directory bundles: entire directory structure
        - Legacy single-file bundles: creates directory with bundle.md inside
        - Registry bundles: resolves cached path first, then copies

        Updates the bundle name in the main bundle file.

        Args:
            source_name: Name of bundle to copy.
            new_name: Name for the new bundle.

        Returns:
            BundleInfo for the new bundle.

        Raises:
            ValueError: If source not found or new name already exists.
        """
        import re

        source_info = self._bundle_info.get(source_name)
        if not source_info:
            raise ValueError(f"Source bundle not found: {source_name}")

        if new_name in self._bundle_info:
            raise ValueError(f"Bundle already exists: {new_name}")

        # Ensure user bundles directory exists
        self._bundles_dir.mkdir(parents=True, exist_ok=True)

        # Target is always a directory
        new_dir = self._bundles_dir / new_name
        if new_dir.exists():
            raise ValueError(f"Bundle directory already exists: {new_dir}")

        # Resolve source path - handle registry bundles specially
        if source_info.source == "registry":
            # Registry bundles need to be loaded to get their cached path
            source_path = await self._resolve_registry_bundle_path(source_name, source_info)
        else:
            source_path = source_info.path

        # Determine bundle structure: directory or single file
        if source_path.is_dir():
            # Directory bundle - copy entire directory
            shutil.copytree(source_path, new_dir)
            # Find the main bundle file
            bundle_md = new_dir / "bundle.md"
            bundle_yaml = new_dir / "bundle.yaml"
            if bundle_md.exists():
                new_bundle_file = bundle_md
            elif bundle_yaml.exists():
                new_bundle_file = bundle_yaml
            else:
                raise ValueError(f"Copied bundle directory missing bundle.md or bundle.yaml: {new_dir}")
        elif source_path.name in ("bundle.md", "bundle.yaml"):
            # Path points to bundle file inside a directory - copy parent directory
            source_dir = source_path.parent
            shutil.copytree(source_dir, new_dir)
            new_bundle_file = new_dir / source_path.name
        else:
            # Legacy single file - create directory structure
            new_dir.mkdir(parents=True)
            new_bundle_file = new_dir / "bundle.md"
            shutil.copy2(source_path, new_bundle_file)

        # Update bundle name in the main file
        content = new_bundle_file.read_text()
        content = re.sub(
            r"(name:\s*)" + re.escape(source_name),
            r"\g<1>" + new_name,
            content,
            count=1,
        )
        new_bundle_file.write_text(content)

        # Register the new bundle (directory URI)
        bundle_uri = f"file://{new_dir.resolve()}"
        self._registry.register({new_name: bundle_uri})

        # Track info
        new_info = BundleInfo(
            name=new_name,
            path=new_bundle_file,
            source="user",
            uri=bundle_uri,
        )
        self._bundle_info[new_name] = new_info

        logger.info(f"Copied bundle {source_name} to {new_name}")
        return new_info

    async def _resolve_registry_bundle_path(self, name: str, info: BundleInfo) -> Path:
        """Resolve the cached filesystem path for a registry bundle.

        Registry bundles are git+ URIs that Foundation caches locally.
        This loads the bundle to get its actual cached path.

        Args:
            name: Bundle name.
            info: BundleInfo with the registry URI.

        Returns:
            Path to the cached bundle file or directory.

        Raises:
            ValueError: If bundle cannot be loaded or path cannot be determined.
        """
        try:
            bundle = await self._registry._load_single(
                name,
                auto_register=False,
                auto_include=False,
            )

            # Get repo root from source_base_paths if available
            repo_root = bundle.source_base_paths.get(bundle.name) if bundle.source_base_paths else None

            if not repo_root and not bundle.base_path:
                raise ValueError(f"Bundle {name} has no base_path after loading")

            uri = info.uri

            # Check if URI has a fragment with subdirectory=
            if "#" in uri and "subdirectory=" in uri.split("#", 1)[1]:
                fragment = uri.split("#", 1)[1]
                if fragment.startswith("subdirectory="):
                    fragment = fragment.split("=", 1)[1]

                # Use repo root from source_base_paths
                if repo_root:
                    path = repo_root / fragment
                elif bundle.base_path:
                    path = bundle.base_path / fragment
                else:
                    raise ValueError(f"Could not determine path for bundle {name}")
            else:
                # No subdirectory fragment - base_path is the bundle location
                path = bundle.base_path

            if path is None:
                raise ValueError(f"Could not determine path for bundle {name}")

            return path

        except Exception as e:
            raise ValueError(f"Failed to resolve registry bundle {name}: {e}")

    async def create_bundle(
        self,
        name: str,
        base_bundle: str | None = None,
        description: str | None = None,
    ) -> BundleInfo:
        """Create a new user bundle.

        Args:
            name: Bundle name (kebab-case).
            base_bundle: Optional bundle to include (extend).
            description: Optional bundle description.

        Returns:
            BundleInfo for the new bundle.

        Raises:
            ValueError: If name already exists.
        """
        if name in self._bundle_info:
            raise ValueError(f"Bundle already exists: {name}")

        # Ensure user bundles directory exists
        self._bundles_dir.mkdir(parents=True, exist_ok=True)

        # Build bundle content
        includes_section = ""
        if base_bundle:
            includes_section = f"\nincludes:\n  - {base_bundle}\n"

        content = f"""---
bundle:
  name: {name}
  version: 1.0.0
  description: {description or f"Custom bundle: {name}"}
{includes_section}---

# {name.replace("-", " ").title()}

Your custom assistant configuration.
"""

        # Write bundle file
        bundle_path = self._bundles_dir / f"{name}.md"
        bundle_path.write_text(content)

        # Register the new bundle
        bundle_uri = f"file://{bundle_path.resolve()}"
        self._registry.register({name: bundle_uri})

        # Track info
        new_info = BundleInfo(
            name=name,
            path=bundle_path,
            source="user",
            uri=bundle_uri,
        )
        self._bundle_info[name] = new_info

        logger.info(f"Created new bundle: {name}")
        return new_info

    def delete_bundle(self, name: str) -> None:
        """Delete a user bundle.

        Args:
            name: Bundle name.

        Raises:
            ValueError: If bundle not found or is a system bundle.
        """
        info = self._bundle_info.get(name)
        if not info:
            raise ValueError(f"Bundle not found: {name}")

        if info.source != "user":
            raise ValueError(f"Cannot delete system bundle: {name}")

        # Delete the file
        if info.path.is_dir():
            shutil.rmtree(info.path)
        else:
            info.path.unlink()

        # Remove from tracking
        del self._bundle_info[name]

        logger.info(f"Deleted bundle: {name}")

    def update_bundle(self, name: str, content: str) -> None:
        """Update a user bundle's content.

        Args:
            name: Bundle name.
            content: New bundle content (markdown with YAML frontmatter).

        Raises:
            ValueError: If bundle not found or is a system bundle.
        """
        info = self._bundle_info.get(name)
        if not info:
            raise ValueError(f"Bundle not found: {name}")

        if info.source != "user":
            raise ValueError(f"Cannot update system bundle: {name}")

        # Write the content
        if info.path.is_dir():
            bundle_file = info.path / "bundle.md"
            bundle_file.write_text(content)
        else:
            info.path.write_text(content)

        logger.info(f"Updated bundle: {name}")

    def rename_bundle(self, old_name: str, new_name: str) -> BundleInfo:
        """Rename a user bundle.

        Args:
            old_name: Current bundle name.
            new_name: New bundle name.

        Returns:
            BundleInfo for the renamed bundle.

        Raises:
            ValueError: If bundle not found, is a system bundle, or new name exists.
        """
        import re

        info = self._bundle_info.get(old_name)
        if not info:
            raise ValueError(f"Bundle not found: {old_name}")

        if info.source != "user":
            raise ValueError(f"Cannot rename system bundle: {old_name}")

        if new_name in self._bundle_info:
            raise ValueError(f"Bundle already exists: {new_name}")

        # Determine old and new paths
        old_path = info.path
        if old_path.is_dir():
            # Directory bundle
            new_path = old_path.parent / new_name
        else:
            # Single file bundle - convert to directory on rename
            new_path = self._bundles_dir / new_name

        if new_path.exists():
            raise ValueError(f"Path already exists: {new_path}")

        # Move/rename the bundle
        if old_path.is_dir():
            old_path.rename(new_path)
            bundle_file = new_path / "bundle.md"
            if not bundle_file.exists():
                bundle_file = new_path / "bundle.yaml"
        else:
            # Single file -> convert to directory
            new_path.mkdir(parents=True)
            new_bundle_file = new_path / "bundle.md"
            shutil.copy2(old_path, new_bundle_file)
            old_path.unlink()
            bundle_file = new_bundle_file

        # Update the name in the bundle file
        if bundle_file.exists():
            content = bundle_file.read_text()
            content = re.sub(
                r"(name:\s*)" + re.escape(old_name),
                r"\g<1>" + new_name,
                content,
                count=1,
            )
            bundle_file.write_text(content)

        # Update tracking
        del self._bundle_info[old_name]
        new_info = BundleInfo(
            name=new_name,
            path=new_path,
            source="user",
            uri=f"file://{new_path.resolve()}",
        )
        self._bundle_info[new_name] = new_info

        # Update registry
        self._registry.register({new_name: new_info.uri})

        logger.info(f"Renamed bundle: {old_name} -> {new_name}")
        return new_info
