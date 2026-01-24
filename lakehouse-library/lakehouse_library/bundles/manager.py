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
        # Derive bundle directories from home_dir to support test isolation
        self._bundles_dir = self._home_dir / "bundles"
        self._share_bundles_dir = self._home_dir / "share" / "bundles"

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
        """Discover and register bundles in well-known bundle directories.

        Scans multiple locations for bundles:
        - ~/.lakehoused/bundles/ (user bundles)
        - ~/.lakehoused/share/bundles/ (system/shared bundles)

        Supports multiple bundle formats:
        - Single .md files (e.g., basic.md) - name derived from filename
        - Directories containing bundle.yaml or bundle.md - name from directory

        Registers each as a local file:// URI.
        """
        # Directories to scan for bundles (in priority order - user bundles first)
        bundle_dirs = [
            (self._bundles_dir, "user"),  # ~/.lakehoused/bundles/
            (self._share_bundles_dir, "system"),  # ~/.lakehoused/share/bundles/
        ]

        discovered: dict[str, str] = {}

        for bundles_dir, source_type in bundle_dirs:
            if not bundles_dir.exists():
                logger.debug(f"Bundles directory does not exist: {bundles_dir}")
                continue

            self._discover_bundles_in_dir(bundles_dir, discovered, source_type=source_type)

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

        # Build includes chain by loading bundles in order
        includes_chain = await self._build_includes_chain(name)

        # Load all bundles in the chain WITHOUT auto-include to track direct declarations
        # This allows us to see which bundle actually declared each component
        bundles_by_name: dict[str, Bundle] = {}
        for bundle_name in includes_chain:
            try:
                # Load with auto_include=False to get ONLY direct declarations
                bundles_by_name[bundle_name] = await self._registry._load_single(
                    bundle_name,
                    auto_register=False,
                    auto_include=False,
                )
            except Exception as e:
                logger.warning(f"Failed to load bundle {bundle_name} in chain: {e}")

        # Track contributions: module_id -> (bundle_name, config)
        def track_modules(module_list: list[dict], bundle_name: str, contributions: dict) -> None:
            """Track which bundle contributed each module."""
            for mod in module_list:
                mod_id = mod.get("module") or mod.get("id", "")
                if mod_id:
                    if mod_id not in contributions:
                        contributions[mod_id] = {"defined_in": bundle_name, "config": mod.get("config")}
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
                            }

        # Process each bundle in chain order to track where components are defined
        provider_contributions: dict[str, Any] = {}
        tool_contributions: dict[str, Any] = {}
        hook_contributions: dict[str, Any] = {}
        agent_contributions: dict[str, Any] = {}

        for bundle_name in includes_chain:
            bundle = bundles_by_name.get(bundle_name)
            if not bundle:
                continue

            track_modules(bundle.providers or [], bundle_name, provider_contributions)
            track_modules(bundle.tools or [], bundle_name, tool_contributions)
            track_modules(bundle.hooks or [], bundle_name, hook_contributions)

            # Track agents (slightly different format)
            for agent_name, agent_config in (bundle.agents or {}).items():
                if agent_name not in agent_contributions:
                    agent_contributions[agent_name] = {
                        "defined_in": bundle_name,
                        "config": agent_config,
                    }
                else:
                    prev = agent_contributions[agent_name]
                    if agent_config != prev.get("config"):
                        agent_contributions[agent_name] = {
                            "defined_in": prev["defined_in"],
                            "overridden": True,
                            "override_in": bundle_name,
                            "original_config": prev.get("config"),
                            "config": agent_config,
                        }

        # Now load the final composed bundle (WITH includes resolved) to get all components
        final_bundle = await self.load_bundle(name)

        # Build resolved module lists with source tracking
        def build_resolved_modules(module_list: list[dict], contributions: dict) -> list[dict]:
            result = []
            for mod in module_list:
                mod_id = mod.get("module") or mod.get("id", "")
                contrib = contributions.get(mod_id, {})
                result.append(
                    {
                        "module": mod_id,
                        "source": mod.get("source"),
                        "config": mod.get("config"),
                        "defined_in": contrib.get("defined_in", name),
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

        return {
            "name": final_bundle.name,
            "source": info.source,
            "includes_chain": includes_chain,
            "session": session_config,
            "providers": build_resolved_modules(final_bundle.providers or [], provider_contributions),
            "tools": build_resolved_modules(final_bundle.tools or [], tool_contributions),
            "hooks": build_resolved_modules(final_bundle.hooks or [], hook_contributions),
            "agents": resolved_agents,
            "instruction": final_bundle.instruction,
        }

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

        try:
            # Load WITHOUT auto_include to see the raw includes list
            bundle = await self._registry._load_single(
                name,
                auto_register=False,
                auto_include=False,
            )
        except Exception:
            return [name]  # Can't load, just return the name

        chain = []

        # Recursively process includes first
        for include in bundle.includes or []:
            sub_chain = await self._build_includes_chain(include, seen)
            for b in sub_chain:
                if b not in chain:
                    chain.append(b)

        # Add this bundle last
        if name not in chain:
            chain.append(name)

        return chain

    def get_bundle_source_content(self, name: str) -> tuple[str, str, str]:
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

        path = info.path

        # Determine format
        if path.is_dir():
            # Directory bundle - look for bundle.md or bundle.yaml
            bundle_md = path / "bundle.md"
            bundle_yaml = path / "bundle.yaml"
            if bundle_md.exists():
                content = bundle_md.read_text()
                file_format = "md"
            elif bundle_yaml.exists():
                content = bundle_yaml.read_text()
                file_format = "yaml"
            else:
                raise ValueError(f"Bundle directory missing bundle.md or bundle.yaml: {path}")
        else:
            content = path.read_text()
            file_format = "md" if path.suffix == ".md" else "yaml"

        return content, str(path), file_format

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

        Args:
            source_name: Name of bundle to copy.
            new_name: Name for the new bundle.

        Returns:
            BundleInfo for the new bundle.

        Raises:
            ValueError: If source not found or new name already exists.
        """
        source_info = self._bundle_info.get(source_name)
        if not source_info:
            raise ValueError(f"Source bundle not found: {source_name}")

        if new_name in self._bundle_info:
            raise ValueError(f"Bundle already exists: {new_name}")

        # Ensure user bundles directory exists
        self._bundles_dir.mkdir(parents=True, exist_ok=True)

        source_path = source_info.path
        new_path = self._bundles_dir / f"{new_name}.md"

        # Read source content
        if source_path.is_dir():
            bundle_file = source_path / "bundle.md"
            if not bundle_file.exists():
                bundle_file = source_path / "bundle.yaml"
            content = bundle_file.read_text()
        else:
            content = source_path.read_text()

        # Update bundle name in content
        # Simple replacement of name in YAML frontmatter
        import re

        content = re.sub(r"(name:\s*)" + re.escape(source_name), r"\g<1>" + new_name, content, count=1)

        # Write new bundle
        new_path.write_text(content)

        # Register the new bundle
        bundle_uri = f"file://{new_path.resolve()}"
        self._registry.register({new_name: bundle_uri})

        # Track info
        new_info = BundleInfo(
            name=new_name,
            path=new_path,
            source="user",
            uri=bundle_uri,
        )
        self._bundle_info[new_name] = new_info

        logger.info(f"Copied bundle {source_name} to {new_name}")
        return new_info

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
