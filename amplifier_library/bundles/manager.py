"""Lakehouse bundle manager - integrates Foundation bundles with Lakehouse sessions.

Wraps Foundation's BundleRegistry to provide:
- Well-known bundle paths at ~/.amplifierd/bundles/
- Runtime config injection for sessions
- Simplified API for session creation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from amplifier_foundation import Bundle
from amplifier_foundation import BundleRegistry

logger = logging.getLogger(__name__)


class LakehouseBundleManager:
    """Manages bundle loading and mount plan generation for Lakehouse.

    Wraps Foundation's BundleRegistry to:
    1. Use ~/.amplifierd/bundles/ as well-known bundle location
    2. Convert bundles to mount plans with runtime config injection
    3. Provide simplified API for session creation

    Example:
        manager = LakehouseBundleManager()
        mount_plan = await manager.generate_mount_plan(
            bundle_ref="software-developer",
            session_id="sess-123",
            amplified_dir="/data/projects/myproject",
        )
    """

    def __init__(self, home_dir: Path | None = None) -> None:
        """Initialize bundle manager.

        Args:
            home_dir: Base directory for Lakehouse data. Defaults to ~/.amplifierd.
                      Bundles are loaded from {home_dir}/bundles/.
        """
        self._home_dir = home_dir or Path.home() / ".amplifierd"
        self._bundles_dir = self._home_dir / "bundles"

        # Initialize Foundation's BundleRegistry with our home directory
        # Foundation uses {home}/cache for remote bundle caching
        self._registry = BundleRegistry(home=self._home_dir)

        # Auto-discover bundles in well-known directory
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
        - ~/.amplifierd/bundles/ (user bundles)
        - ~/.amplifierd/share/bundles/ (system/shared bundles)

        Supports multiple bundle formats:
        - Single .md files (e.g., basic.md) - name derived from filename
        - Directories containing bundle.yaml or bundle.md - name from directory

        Registers each as a local file:// URI.
        """
        # Directories to scan for bundles (in priority order - user bundles first)
        bundle_dirs = [
            self._bundles_dir,  # ~/.amplifierd/bundles/
            self._home_dir / "share" / "bundles",  # ~/.amplifierd/share/bundles/
        ]

        discovered: dict[str, str] = {}

        for bundles_dir in bundle_dirs:
            if not bundles_dir.exists():
                logger.debug(f"Bundles directory does not exist: {bundles_dir}")
                continue

            self._discover_bundles_in_dir(bundles_dir, discovered)

        if discovered:
            self._registry.register(discovered)
            logger.info(f"Discovered {len(discovered)} local bundles")

    def _discover_bundles_in_dir(
        self, bundles_dir: Path, discovered: dict[str, str], prefix: str = ""
    ) -> None:
        """Discover bundles in a directory, recursively scanning subdirectories.

        Args:
            bundles_dir: Directory to scan.
            discovered: Dict to update with discovered bundles (name -> URI).
            prefix: Prefix for nested bundles (e.g., "foundation/" for foundation/base.md).
        """
        for item in bundles_dir.iterdir():
            if item.is_file() and item.suffix == ".md":
                # Single .md file bundle (e.g., basic.md, software-developer.md)
                bundle_name = prefix + item.stem  # Remove .md extension
                bundle_uri = f"file://{item.resolve()}"

                # Don't overwrite if already discovered (user bundles take priority)
                if bundle_name not in discovered:
                    discovered[bundle_name] = bundle_uri
                    logger.debug(f"Discovered bundle file: {bundle_name} -> {bundle_uri}")

            elif item.is_dir():
                # Check if it's a bundle directory (contains bundle.md or bundle.yaml)
                bundle_md = item / "bundle.md"
                bundle_yaml = item / "bundle.yaml"

                if bundle_md.exists() or bundle_yaml.exists():
                    # Directory-style bundle
                    bundle_name = prefix + item.name
                    bundle_uri = f"file://{item.resolve()}"

                    if bundle_name not in discovered:
                        discovered[bundle_name] = bundle_uri
                        logger.debug(f"Discovered bundle dir: {bundle_name} -> {bundle_uri}")
                else:
                    # Recurse into subdirectory (e.g., foundation/)
                    self._discover_bundles_in_dir(item, discovered, prefix=prefix + item.name + "/")

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
        return bundle.to_mount_plan()

    async def generate_mount_plan(
        self,
        bundle_ref: str,
        session_id: str,
        amplified_dir: str,
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
            amplified_dir: Absolute path to the amplified directory.
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
            amplified_dir=amplified_dir,
            api_key=api_key,
        )

        return mount_plan

    def _inject_runtime_config(
        self,
        mount_plan: dict[str, Any],
        session_id: str,
        amplified_dir: str,
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
            amplified_dir: Absolute path to amplified directory.
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
                    tool["config"]["working_dir"] = amplified_dir

                # For filesystem tools, inject allowed_write_paths
                tool_module = tool.get("module", "") or tool.get("id", "")
                tool_source = tool.get("source", "")
                is_filesystem_tool = "tool-filesystem" in tool_module or "filesystem" in tool_source

                if is_filesystem_tool and "allowed_write_paths" not in tool["config"]:
                    tool["config"]["allowed_write_paths"] = [amplified_dir]

        # Inject into hooks
        if "hooks" in mount_plan:
            for hook in mount_plan["hooks"]:
                if "config" not in hook:
                    hook["config"] = {}

                # Set session_log_template for logging hooks
                hook_module = hook.get("module", "") or hook.get("id", "")
                hook_source = hook.get("source", "")
                is_logging_hook = "logging" in hook_module or "logging" in hook_source

                if is_logging_hook and "session_log_template" not in hook["config"]:
                    hook["config"]["session_log_template"] = str(
                        self._home_dir / "state" / "sessions" / session_id / "session.log"
                    )

        # Inject API key into providers
        if api_key and "providers" in mount_plan:
            for provider in mount_plan["providers"]:
                if "config" not in provider:
                    provider["config"] = {}

                if "api_key" not in provider["config"]:
                    provider["config"]["api_key"] = api_key

        return mount_plan

    def list_available_bundles(self) -> list[str]:
        """List all available bundle names.

        Returns:
            Sorted list of registered bundle names.
        """
        return self._registry.list_registered()
