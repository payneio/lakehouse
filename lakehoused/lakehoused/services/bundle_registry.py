"""Bundle registry service - manages bundle registration from BUNDLES.txt.

This service owns all bundle registry operations, treating:
- BUNDLES.txt: Declarative config (what user wants) - source of truth
- Foundation registry: Runtime cache (loaded state, paths, timestamps)

The service ensures these two stores stay in sync.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from lakehoused.storage.paths import get_bundles_dir

if TYPE_CHECKING:
    from lakehoused.bundles import LakehouseBundleManager

logger = logging.getLogger(__name__)


DEFAULT_BUNDLES_TXT = """\
# Amplifier Foundation bundles
# Format: name:git+https://github.com/owner/repo@branch#subdirectory=path/to/bundle.md
# Note: Fragment format follows pip/uv standard with subdirectory= prefix
#
# Foundation handles git cloning/caching to ~/.amplifier/cache/
# This preserves full repo structure for namespace:path resolution
#
# Foundation namespace (required for namespace:path includes like foundation:behaviors/logging)
foundation:git+https://github.com/microsoft/amplifier-foundation@main
amplifier-dev:git+https://github.com/microsoft/amplifier-foundation@main#subdirectory=bundles/amplifier-dev.yaml
minimal:git+https://github.com/microsoft/amplifier-foundation@main#subdirectory=bundles/minimal.yaml

# Personal bundles (payneio/payne-amplifier)
# payne-amplifier namespace (required for namespace:path includes like payne-amplifier:behaviors/software-development)
payne-amplifier:git+https://github.com/payneio/payne-amplifier@main
software-developer:git+https://github.com/payneio/payne-amplifier@main#subdirectory=bundles/software-developer.md
basic:git+https://github.com/payneio/payne-amplifier@main#subdirectory=bundles/basic.md
"""


class BundleRegistryService:
    """Manages bundle registry with BUNDLES.txt as source of truth.

    BUNDLES.txt: Declarative config (what user wants)
    Foundation registry: Runtime cache (loaded state, paths, timestamps)

    This service coordinates both stores to keep them in sync.

    Example:
        service = BundleRegistryService()
        service.add("my-bundle", "git+https://github.com/user/repo@main#subdirectory=bundles/my.md")
        service.remove("my-bundle")
        entries = service.get_entries()
    """

    _instance: BundleRegistryService | None = None

    def __init__(self, bundles_file: Path | None = None) -> None:
        """Initialize the bundle registry service.

        Args:
            bundles_file: Path to BUNDLES.txt. Defaults to ~/.lakehoused/share/bundles/BUNDLES.txt.
        """
        self._bundles_file: Path = bundles_file if bundles_file is not None else get_bundles_dir() / "BUNDLES.txt"
        self._entries: dict[str, str] = {}
        self._load_config()

    @classmethod
    def get_instance(cls) -> BundleRegistryService:
        """Get the singleton instance of the service.

        Returns:
            The singleton BundleRegistryService instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    @property
    def bundles_file(self) -> Path:
        """Path to BUNDLES.txt file."""
        return self._bundles_file

    def _load_config(self) -> None:
        """Load entries from BUNDLES.txt.

        Creates BUNDLES.txt with defaults if it doesn't exist.
        """
        self._ensure_bundles_file()
        self._entries = self._parse_bundles_file()
        if self._entries:
            logger.info(f"Loaded {len(self._entries)} bundles from BUNDLES.txt")

    def _ensure_bundles_file(self) -> None:
        """Create BUNDLES.txt with defaults if it doesn't exist."""
        if not self._bundles_file.exists():
            self._bundles_file.parent.mkdir(parents=True, exist_ok=True)
            self._bundles_file.write_text(DEFAULT_BUNDLES_TXT)
            logger.info(f"Created default BUNDLES.txt at {self._bundles_file}")

    def _parse_bundles_file(self) -> dict[str, str]:
        """Parse BUNDLES.txt and return name->URI mappings.

        Returns:
            Dict mapping bundle name to git+ URI.
        """
        bundles: dict[str, str] = {}

        for line in self._bundles_file.read_text().splitlines():
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse name:git_ref format
            if ":" not in line:
                logger.warning(f"Invalid BUNDLES.txt line (missing ':'): {line}")
                continue

            try:
                name, git_ref = line.split(":", 1)
                name = name.strip()
                git_ref = git_ref.strip()

                if not name or not git_ref:
                    logger.warning(f"Invalid BUNDLES.txt line (empty name or ref): {line}")
                    continue

                bundles[name] = git_ref
            except ValueError:
                logger.warning(f"Invalid BUNDLES.txt line: {line}")
                continue

        return bundles

    def _save_config(self) -> None:
        """Save current entries back to BUNDLES.txt.

        Preserves comments and structure, updates/adds/removes entries.
        """
        # Read existing lines to preserve comments
        if self._bundles_file.exists():
            existing_lines = self._bundles_file.read_text().splitlines()
        else:
            existing_lines = []

        # Track which entries we've written
        written_entries: set[str] = set()
        new_lines: list[str] = []

        for line in existing_lines:
            stripped = line.strip()

            # Keep comments and empty lines
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            # Parse entry
            if ":" in stripped:
                entry_name = stripped.split(":", 1)[0].strip()

                if entry_name in self._entries:
                    # Update existing entry
                    new_lines.append(f"{entry_name}:{self._entries[entry_name]}")
                    written_entries.add(entry_name)
                # else: entry was removed, don't add it back
            else:
                # Malformed line, keep as-is
                new_lines.append(line)

        # Add any new entries not in the original file
        for name, uri in self._entries.items():
            if name not in written_entries:
                new_lines.append(f"{name}:{uri}")

        # Write back
        content = "\n".join(new_lines)
        if not content.endswith("\n"):
            content += "\n"
        self._bundles_file.write_text(content)

    def get_entries(self) -> dict[str, str]:
        """Get all bundle name->URI mappings.

        Returns:
            Copy of the entries dict.
        """
        return self._entries.copy()

    def has_entry(self, name: str) -> bool:
        """Check if a bundle entry exists.

        Args:
            name: Bundle name.

        Returns:
            True if entry exists.
        """
        return name in self._entries

    def get_entry(self, name: str) -> str | None:
        """Get a bundle entry by name.

        Args:
            name: Bundle name.

        Returns:
            Git URL if found, None otherwise.
        """
        return self._entries.get(name)

    def add(self, name: str, git_url: str, bundle_manager: LakehouseBundleManager | None = None) -> None:
        """Add a bundle to the registry.

        Updates both BUNDLES.txt (config) and optionally registers with Foundation.

        Args:
            name: Bundle name (kebab-case).
            git_url: Git URL (e.g., git+https://github.com/owner/repo@branch#subdirectory=path).
            bundle_manager: Optional LakehouseBundleManager to register with Foundation.

        Raises:
            ValueError: If bundle name already exists or URL is invalid.
        """
        if name in self._entries:
            raise ValueError(f"Bundle already exists: {name}")

        if not git_url.startswith("git+"):
            raise ValueError("Git URL must start with 'git+' (e.g., git+https://github.com/...)")

        # Add to config
        self._entries[name] = git_url
        self._save_config()
        logger.info(f"Added bundle entry: {name}:{git_url}")

        # Register with Foundation if manager provided
        if bundle_manager:
            bundle_manager.registry.register({name: git_url})

    def remove(self, name: str, bundle_manager: LakehouseBundleManager | None = None) -> None:
        """Remove a bundle from the registry.

        Updates both BUNDLES.txt (config) and optionally unregisters from Foundation.

        Args:
            name: Bundle name to remove.
            bundle_manager: Optional LakehouseBundleManager to unregister from Foundation.

        Raises:
            ValueError: If bundle name not found.
        """
        if name not in self._entries:
            raise ValueError(f"Bundle not found: {name}")

        # Remove from config
        del self._entries[name]
        self._save_config()
        logger.info(f"Removed bundle entry: {name}")

        # Unregister from Foundation if manager provided
        if bundle_manager:
            bundle_manager.unregister_bundle(name)

    def sync_to_foundation(self, bundle_manager: LakehouseBundleManager) -> None:
        """Ensure Foundation registry matches BUNDLES.txt config.

        Registers all entries from BUNDLES.txt with Foundation.
        Called on startup to sync config with runtime state.

        Args:
            bundle_manager: LakehouseBundleManager to register bundles with.
        """
        if self._entries:
            bundle_manager.registry.register(self._entries)
            logger.info(f"Synced {len(self._entries)} bundles to Foundation registry")

    def reload(self) -> None:
        """Reload entries from BUNDLES.txt.

        Useful after external modifications to the file.
        """
        self._entries = self._parse_bundles_file()
        logger.info(f"Reloaded {len(self._entries)} bundles from BUNDLES.txt")
