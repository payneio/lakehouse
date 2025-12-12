"""Module source resolver for amplifierd.

Resolves module IDs to filesystem paths in the compiled profile structure.
Uses flat profile organization (no collections) with behavior-aware resolution.

Contract:
- Inputs: Module ID (hyphenated), profile ID (source hint)
- Outputs: Path to directory containing Python package
- Side Effects: None (read-only discovery)
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ModuleSource:
    """File-based module source for amplifierd."""

    def __init__(self, path: Path, module_id: str):
        """Initialize module source.

        Args:
            path: Path to directory containing module package
            module_id: Module identifier for logging
        """
        self.path = path
        self.module_id = module_id

    def resolve(self) -> Path:
        """Resolve to filesystem path.

        Returns:
            Path to directory containing importable Python module

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Module path not found: {self.path}")
        return self.path

    def __str__(self) -> str:
        return f"FileSource({self.module_id} @ {self.path})"


class DaemonModuleSourceResolver:
    """Resolves module IDs to paths in compiled profile structure (v3).

    Uses flat profile organization without collections.
    Searches both session/ and behaviors/*/ directories.

    Example:
        >>> resolver = DaemonModuleSourceResolver(share_dir=Path(".amplifierd/share"))
        >>> source = resolver.resolve("provider-anthropic", "software-developer")
        >>> path = source.resolve()
        >>> # Returns: .amplifierd/share/profiles/software-developer/session/providers/provider-anthropic
    """

    # Map module ID patterns to component types
    TYPE_PATTERNS = {
        "provider-": "providers",
        "tool-": "tools",
        "hooks-": "hooks",
        "loop-": "orchestrator",
        "orchestrator-": "orchestrator",
        "context-": "context",
    }

    def __init__(self, share_dir: Path):
        """Initialize resolver with share directory.

        Args:
            share_dir: Path to amplifierd share directory
        """
        self.share_dir = Path(share_dir)
        logger.debug(f"DaemonModuleSourceResolver initialized with share_dir={self.share_dir}")

    def resolve(
        self,
        module_id: str,
        profile_hint: str | None = None,
        component_type: str | None = None,
    ) -> ModuleSource:
        """Resolve module ID to source path.

        Args:
            module_id: Hyphenated module name (e.g., "provider-anthropic")
            profile_hint: Profile ID (e.g., "software-developer")
            component_type: Known component type ('hooks', 'tools', 'providers', 'context', 'orchestrator')
                           If provided, uses this type directly, skipping inference.
                           If None, falls back to name-based inference.

        Returns:
            ModuleSource that can be resolved to a Path

        Raises:
            ValueError: If profile hint missing
            FileNotFoundError: If module not found in profile

        Example:
            >>> # When you know the component type (from mount plan)
            >>> resolver.resolve("streaming-ui", "software-developer", component_type="hooks")
            ModuleSource(.../.amplifierd/share/profiles/software-developer/.../hooks/streaming-ui)

            >>> # Backwards compatible - infers from name
            >>> resolver.resolve("provider-anthropic", "software-developer")
            ModuleSource(.../.amplifierd/share/profiles/software-developer/.../providers/provider-anthropic)
        """
        if not profile_hint:
            raise ValueError("profile_hint (profile ID) is required for v3 profiles")

        # Profile hint is just the profile ID (no collections)
        profile_id = profile_hint

        # Use provided component type if available, otherwise infer from module ID
        if component_type:
            logger.debug(f"Using provided component type '{component_type}' for module '{module_id}'")
            resolved_type = component_type
        else:
            resolved_type = self._infer_component_type(module_id)
            logger.debug(f"Inferred component type '{resolved_type}' from module ID '{module_id}'")

        # Build profile directory path
        profile_dir = self.share_dir / "profiles" / profile_id

        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile '{profile_id}' not found at {profile_dir}")

        # Check session components first
        session_path = profile_dir / "session" / resolved_type / module_id
        if session_path.exists():
            logger.debug(f"Resolved '{module_id}' → {session_path} (session component)")
            return ModuleSource(path=session_path, module_id=module_id)

        # Check behavior components (search all behaviors)
        for behavior_dir in profile_dir.glob("behaviors/*/"):
            behavior_path = behavior_dir / resolved_type / module_id
            if behavior_path.exists():
                logger.debug(f"Resolved '{module_id}' → {behavior_path} (behavior: {behavior_dir.name})")
                return ModuleSource(path=behavior_path, module_id=module_id)

        # Module not found
        available_dirs = list(profile_dir.glob(f"*/{resolved_type}/*")) + list(
            profile_dir.glob(f"behaviors/*/{resolved_type}/*")
        )
        available_modules = [d.name for d in available_dirs if d.is_dir()]

        raise FileNotFoundError(
            f"Module '{module_id}' not found in profile '{profile_id}'.\n"
            f"Searched in: session/{resolved_type}/ and behaviors/*/{resolved_type}/\n"
            f"Available {resolved_type}: {', '.join(available_modules) if available_modules else 'none'}"
        )

    def _infer_component_type(self, module_id: str) -> str:
        """Infer component type from module ID.

        Note: This is a fallback when component_type is not explicitly provided.
        Prefer passing component_type directly when known.

        Args:
            module_id: Hyphenated module name

        Returns:
            Component type directory name (e.g., "tools", "providers")

        Example:
            >>> resolver._infer_component_type("provider-anthropic")
            'providers'
            >>> resolver._infer_component_type("tool-bash")
            'tools'
            >>> resolver._infer_component_type("hooks-logging")
            'hooks'
        """
        # Check patterns in order
        for pattern, type_name in self.TYPE_PATTERNS.items():
            if module_id.startswith(pattern):
                return type_name

        # Handle special cases
        if module_id in ["loop-streaming", "loop-basic", "loop-events"]:
            return "orchestrator"
        if "context" in module_id:
            return "context"

        # Default to tools
        logger.warning(
            f"Could not infer component type for '{module_id}', defaulting to 'tools'. "
            f"Consider passing component_type explicitly to resolve() for better accuracy."
        )
        return "tools"
