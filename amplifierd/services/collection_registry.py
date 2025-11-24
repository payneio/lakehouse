"""Collection registry for tracking installed collections.

Maintains collections.yaml registry with metadata about installed collections
and their extracted resources.
"""

import logging
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CollectionResourceInfo:
    """Information about resources in a collection."""

    modules: list[str]
    profiles: list[str]
    agents: list[str]
    context: list[str]


@dataclass
class CollectionRegistryEntry:
    """Registry entry for an installed collection."""

    version: str
    source: str
    installed_at: str
    resources: CollectionResourceInfo
    package_bundled: bool = False


class CollectionRegistry:
    """Registry for tracking installed collections.

    Manages collections.yaml file that tracks:
    - Which collections are installed
    - Where they came from (source)
    - What version was installed
    - What resources were extracted
    """

    def __init__(self, share_dir: Path) -> None:
        """Initialize collection registry.

        Args:
            share_dir: Root share directory containing collections.yaml
        """
        self.share_dir = Path(share_dir)
        self.registry_file = self.share_dir / "collections.yaml"
        self.share_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CollectionRegistry initialized with share_dir={self.share_dir}")

    def load(self) -> dict[str, CollectionRegistryEntry]:
        """Load registry from collections.yaml.

        Returns:
            Dictionary mapping collection name to registry entry
        """
        if not self.registry_file.exists():
            logger.debug("Registry file does not exist, returning empty registry")
            return {}

        try:
            with open(self.registry_file) as f:
                data = yaml.safe_load(f)

            if not data or "collections" not in data:
                return {}

            collections = {}
            for name, entry_data in data["collections"].items():
                resources_data = entry_data.get("resources", {})
                resources = CollectionResourceInfo(
                    modules=resources_data.get("modules", []),
                    profiles=resources_data.get("profiles", []),
                    agents=resources_data.get("agents", []),
                    context=resources_data.get("context", []),
                )

                # Infer package_bundled from source if not explicitly set
                source = entry_data.get("source", "")
                package_bundled = entry_data.get("package_bundled", source.startswith("bundled:"))

                collections[name] = CollectionRegistryEntry(
                    version=entry_data.get("version", "0.0.0"),
                    source=source,
                    installed_at=entry_data.get("installed_at", ""),
                    resources=resources,
                    package_bundled=package_bundled,
                )

            logger.info(f"Loaded {len(collections)} collections from registry")
            return collections

        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            return {}

    def save(self, collections: dict[str, CollectionRegistryEntry]) -> None:
        """Save registry to collections.yaml.

        Args:
            collections: Dictionary mapping collection name to registry entry
        """
        try:
            data = {
                "collections": {
                    name: {
                        "version": entry.version,
                        "source": entry.source,
                        "installed_at": entry.installed_at,
                        "resources": asdict(entry.resources),
                        "package_bundled": entry.package_bundled,
                    }
                    for name, entry in collections.items()
                }
            }

            with open(self.registry_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Saved {len(collections)} collections to registry")

        except Exception as e:
            logger.error(f"Error saving registry: {e}")
            raise

    def add_collection(
        self, name: str, source: str, version: str, resources: CollectionResourceInfo, package_bundled: bool = False
    ) -> None:
        """Add or update collection in registry.

        Args:
            name: Collection name
            source: Source URL or path
            version: Collection version
            resources: Extracted resources
            package_bundled: Whether collection is bundled with package
        """
        collections = self.load()

        collections[name] = CollectionRegistryEntry(
            version=version,
            source=source,
            installed_at=datetime.now().isoformat(),
            resources=resources,
            package_bundled=package_bundled,
        )

        self.save(collections)
        logger.info(f"Added collection to registry: {name}")

    def remove_collection(self, name: str) -> CollectionResourceInfo | None:
        """Remove collection from registry and return its resources.

        Args:
            name: Collection name

        Returns:
            CollectionResourceInfo if collection was found, None otherwise
        """
        collections = self.load()

        if name not in collections:
            logger.warning(f"Collection not found in registry: {name}")
            return None

        entry = collections[name]
        del collections[name]

        self.save(collections)
        logger.info(f"Removed collection from registry: {name}")

        return entry.resources

    def get_collection(self, name: str) -> CollectionRegistryEntry | None:
        """Get collection entry from registry.

        Args:
            name: Collection name

        Returns:
            CollectionRegistryEntry if found, None otherwise
        """
        collections = self.load()
        return collections.get(name)

    def list_collections(self) -> list[tuple[str, CollectionRegistryEntry]]:
        """List all registered collections.

        Returns:
            List of (name, entry) tuples
        """
        collections = self.load()
        return list(collections.items())

    def initialize_with_defaults(self) -> None:
        """Initialize collections.yaml with package-bundled collections if empty.

        Seeds with minimal declarative entries - sync process will populate full details.
        """
        if self.registry_file.exists():
            # Check if it's truly empty
            with open(self.registry_file) as f:
                data = yaml.safe_load(f)
            if data and data.get("collections"):
                logger.debug("Collections registry already initialized")
                return

        package_dir = Path(__file__).parent.parent
        collections_dir = package_dir / "data" / "collections"

        if not collections_dir.exists():
            logger.debug("No package collections to seed")
            return

        # Build minimal declarative entries
        seed_data = {"collections": {}}

        for dir_path in collections_dir.iterdir():
            if not dir_path.is_dir() or dir_path.name.startswith((".", "_")):
                continue

            has_resources = any((dir_path / subdir).is_dir() for subdir in ["modules", "profiles", "agents", "context"])

            if not has_resources:
                continue

            # Minimal entry - just source field
            seed_data["collections"][dir_path.name] = {"source": f"bundled:amplifierd.data.collections.{dir_path.name}"}

        if seed_data["collections"]:
            with open(self.registry_file, "w") as f:
                yaml.dump(seed_data, f, default_flow_style=False, sort_keys=False)

            logger.info(
                f"Initialized collections.yaml with {len(seed_data['collections'])} package-bundled collection(s)"
            )
