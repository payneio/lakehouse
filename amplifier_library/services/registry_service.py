"""Registry service for v3 profile system.

Handles loading and resolving component registries.
"""

import logging
from pathlib import Path

import yaml

from amplifier_library.models.registries import Registry, RegistriesConfig

logger = logging.getLogger(__name__)


class RegistryService:
    """Service for loading and managing component registries."""

    def __init__(self, share_dir: Path):
        """Initialize registry service.

        Args:
            share_dir: Share directory (contains registries.yaml)
        """
        self.share_dir = share_dir
        self.registries_file = share_dir / "registries.yaml"
        self._registries: dict[str, Registry] | None = None

    def load_registries(self, force_reload: bool = False) -> dict[str, Registry]:
        """Load registries from registries.yaml.

        Args:
            force_reload: Force reload even if already cached

        Returns:
            Dictionary mapping registry ID to Registry object
        """
        if self._registries is not None and not force_reload:
            return self._registries

        if not self.registries_file.exists():
            logger.info(f"No registries.yaml found at {self.registries_file}, using empty registries")
            self._registries = {}
            return self._registries

        try:
            data = yaml.safe_load(self.registries_file.read_text())
            config = RegistriesConfig(**data)

            self._registries = {reg.id: reg for reg in config.registries}

            logger.info(f"Loaded {len(self._registries)} registries from {self.registries_file}")
            for reg_id, reg in self._registries.items():
                logger.debug(f"  Registry '{reg_id}': {reg.uri}")

            return self._registries

        except Exception as e:
            logger.error(f"Failed to load registries from {self.registries_file}: {e}")
            self._registries = {}
            return self._registries

    def resolve_amp_uri(self, source: str) -> str:
        """Resolve amp:// URI to full git+/file:// URI.

        Args:
            source: Source URI (may be amp://, git+, http://, or file://)

        Returns:
            Resolved URI (amp:// converted to full URI, others pass through)

        Raises:
            ValueError: If amp:// registry not found
        """
        # If not amp:// URI, return as-is (supports git+/http://file:// URIs)
        if not source.startswith("amp://"):
            return source

        # Ensure registries are loaded
        registries = self.load_registries()

        # Parse amp://registry-id/path/to/component
        parts = source[6:].split("/", 1)  # Remove "amp://"
        registry_id = parts[0]
        component_path = parts[1] if len(parts) > 1 else ""

        # Look up registry
        if registry_id not in registries:
            available = ", ".join(registries.keys()) if registries else "none"
            raise ValueError(
                f"Unknown registry '{registry_id}' in URI '{source}'. " f"Available registries: {available}"
            )

        registry = registries[registry_id]

        # Construct full URI: registry_uri + component_path
        resolved = f"{registry.uri.rstrip('/')}/{component_path}"
        logger.debug(f"Resolved amp:// URI: {source} → {resolved}")

        return resolved

    def ensure_default_registries(self):
        """Create default registries.yaml if it doesn't exist."""
        if self.registries_file.exists():
            return

        logger.info(f"Creating default registries.yaml at {self.registries_file}")

        default_registries = {
            "registries": [
                {
                    "id": "lakehouse",
                    "uri": "/data/repos/lakehouse/registry",
                    "description": "Lakehouse local component registry",
                }
            ]
        }

        self.registries_file.parent.mkdir(parents=True, exist_ok=True)
        self.registries_file.write_text(yaml.dump(default_registries, default_flow_style=False))

        logger.info("Created default registries.yaml")
