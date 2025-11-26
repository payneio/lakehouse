"""Simple collection management service.

Lists collections from registry, mounts via git clone or filesystem copy,
and unmounts via directory removal.

Unified service that manages both registry persistence and collection operations.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from amplifier_library.storage.paths import get_cache_dir
from amplifier_library.storage.paths import get_state_dir
from amplifierd.models.collections import CollectionInfo

if TYPE_CHECKING:
    from amplifierd.services.profile_compilation import ProfileCompilationService
    from amplifierd.services.profile_discovery import ProfileDiscoveryService

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

    source: str
    installed_at: str


class CollectionService:
    """Simple collection management service.

    Unified service that manages:
    - Registry persistence (collections.yaml)
    """

    def __init__(
        self,
        share_dir: Path,
        discovery_service: ProfileDiscoveryService | None = None,
        compilation_service: ProfileCompilationService | None = None,
    ) -> None:
        """Initialize collection service.

        Args:
            share_dir: Root share directory for resources
            discovery_service: Optional ProfileDiscoveryService for auto-discovering profiles
            compilation_service: Optional ProfileCompilationService for auto-compiling profiles
        """
        self.share_dir = Path(share_dir)
        self.share_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.share_dir / "collections.yaml"

        self.git_cache_dir = get_cache_dir() / "git"
        self.git_cache_dir.mkdir(parents=True, exist_ok=True)

        self.collections_cache_dir = self.share_dir / "profiles"
        self.collections_cache_dir.mkdir(parents=True, exist_ok=True)

        self.state_dir = get_state_dir()
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # In-memory registry state
        self._collections: dict[str, CollectionRegistryEntry] = {}

        # Profile services for auto-discovery and compilation
        self.discovery_service = discovery_service
        self.compilation_service = compilation_service

        # Load registry and initialize with defaults if needed
        self._load_registry()

        services_status = []
        if discovery_service:
            services_status.append("profile-discovery")
        if compilation_service:
            services_status.append("profile-compilation")

        services_str = f" (with {', '.join(services_status)})" if services_status else ""
        logger.info(
            f"SimpleCollectionService initialized with share_dir={self.share_dir}, "
            f"state_dir={self.state_dir}{services_str}"
        )

    # Registry persistence methods

    def _load_registry(self) -> None:
        """Load registry from collections.yaml into memory."""
        if not self.registry_file.exists():
            logger.debug("Registry file does not exist, starting with empty registry")
            self._collections = {}
            return

        try:
            with open(self.registry_file) as f:
                data = yaml.safe_load(f)

            if not data or "collections" not in data:
                self._collections = {}
                return

            self._collections = {}
            for name, entry_data in data["collections"].items():
                self._collections[name] = CollectionRegistryEntry(
                    source=entry_data.get("source", ""),
                    installed_at=entry_data.get("installed_at", ""),
                )

            logger.info(f"Loaded {len(self._collections)} collections from registry")

        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            self._collections = {}

    def _save_registry(self) -> None:
        """Save in-memory registry to collections.yaml."""
        try:
            data = {
                "collections": {
                    name: {
                        "source": entry.source,
                        "installed_at": entry.installed_at,
                    }
                    for name, entry in self._collections.items()
                }
            }

            with open(self.registry_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Saved {len(self._collections)} collections to registry")

        except Exception as e:
            logger.error(f"Error saving registry: {e}")
            raise

    # Registry query methods

    def get_collection(self, identifier: str) -> CollectionRegistryEntry | None:
        """Get collection entry from registry.

        Args:
            identifier: Collection identifier

        Returns:
            CollectionRegistryEntry if found, None otherwise
        """
        return self._collections.get(identifier)

    def list_collection_entries(self) -> list[tuple[str, CollectionRegistryEntry]]:
        """List all registered collection entries.

        Returns:
            List of (name, entry) tuples
        """
        return list(self._collections.items())

    def _add_collection_to_registry(
        self,
        name: str,
        source: str,
    ) -> None:
        """Add or update collection in registry.

        Args:
            name: Collection name
            source: Source URL or path
        """
        self._collections[name] = CollectionRegistryEntry(
            source=source,
            installed_at=datetime.now().isoformat(),
        )

        self._save_registry()
        logger.info(f"Added collection to registry: {name}")

    def _remove_collection_from_registry(self, name: str) -> bool:
        """Remove collection from registry.

        Args:
            name: Collection name

        Returns:
            True if collection was found and removed, False otherwise
        """
        if name not in self._collections:
            logger.warning(f"Collection not found in registry: {name}")
            return False

        del self._collections[name]
        self._save_registry()
        logger.info(f"Removed collection from registry: {name}")
        return True

    # High-level collection operations

    def list_collections(self) -> list[CollectionInfo]:
        """List all collections from registry.

        Returns:
            List of CollectionInfo objects
        """
        collections = []

        for name, entry in self._collections.items():
            # For now, create basic collection info
            # Full profile metadata will come from profile files
            collections.append(
                CollectionInfo(
                    identifier=name,
                    source=entry.source,
                    profiles=[],  # Profiles loaded separately
                )
            )

        logger.info(f"Found {len(collections)} collections")
        return collections

    def get_collection_info(self, identifier: str) -> CollectionInfo:
        """Get detailed information about a collection.

        Args:
            identifier: Collection identifier

        Returns:
            CollectionInfo object

        Raises:
            FileNotFoundError: If collection does not exist
        """
        entry = self.get_collection(identifier)
        if not entry:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        return CollectionInfo(
            identifier=identifier,
            source=entry.source,
            profiles=[],  # Profiles loaded separately
        )

    def mount_collection(self, identifier: str, source: str) -> None:
        """Mount a collection from a source.

        Source can be:
        - git+URL: Clones repository to cache
        - /path/to/dir: Uses local filesystem path

        Args:
            identifier: Collection identifier (directory name)
            source: Git URL (git+...) or local filesystem path

        Raises:
            ValueError: If collection already exists
            RuntimeError: If mounting fails
        """
        if self.get_collection(identifier):
            raise ValueError(f"Collection already exists: {identifier}")

        try:
            if source.startswith("git+"):
                # Clone/cache the git repository
                self._clone_to_cache(identifier, source)
            else:
                # Local filesystem path - validate it exists
                source_path = Path(source)
                if not source_path.exists():
                    raise FileNotFoundError(f"Source directory not found: {source}")
                if not source_path.is_dir():
                    raise ValueError(f"Source is not a directory: {source}")

            # Add to registry
            self._add_collection_to_registry(
                name=identifier,
                source=source,
            )

            logger.info(f"Successfully mounted collection {identifier} from {source}")

        except Exception as e:
            raise RuntimeError(f"Failed to mount collection {identifier}: {e}") from e

    def unmount_collection(self, identifier: str) -> None:
        """Unmount a collection.

        Args:
            identifier: Collection identifier

        Raises:
            FileNotFoundError: If collection does not exist
        """
        if not self._remove_collection_from_registry(identifier):
            raise FileNotFoundError(f"Collection not found: {identifier}")

        self._remove_resources(identifier)
        logger.info(f"Successfully unmounted collection {identifier}")

    def _resolve_profile_dependencies(self, profiles: list[str], collection: str) -> None:
        """Resolve module dependencies for all profiles.

        Args:
            profiles: List of profile paths relative to share_dir
            collection: Collection name for module namespace
        """
        from .module_resolver_service import get_module_resolver_service

        resolver = get_module_resolver_service()
        for profile_rel_path in profiles:
            profile_path = self.share_dir / profile_rel_path
            try:
                resolver.resolve_module_dependencies(profile_path, collection)
            except Exception as e:
                logger.warning(f"Failed to resolve dependencies for profile {profile_rel_path}: {e}")

    def _remove_resources(self, identifier: str) -> None:
        """Remove extracted resources for a collection.

        Args:
            identifier: Collection identifier
        """
        for resource_type in ["modules", "profiles", "agents", "context"]:
            resource_dir = self.share_dir / resource_type / identifier
            if resource_dir.exists():
                shutil.rmtree(resource_dir)
                logger.debug(f"Removed {resource_type} for {identifier}")

    def _rollback_resources(self, identifier: str) -> None:
        """Rollback partially extracted resources after failed mount.

        Args:
            identifier: Collection identifier
        """
        for resource_type in ["modules", "profiles", "agents", "context"]:
            resource_dir = self.share_dir / resource_type / identifier
            if resource_dir.exists():
                shutil.rmtree(resource_dir)
                logger.debug(f"Rolled back {resource_type} for {identifier}")

    # Git and filesystem operations

    def _mount_git(self, source: str, dest: Path) -> None:
        """Mount collection via git clone.

        Args:
            source: Git repository URL
            dest: Destination directory

        Raises:
            RuntimeError: If git clone fails
        """
        result = subprocess.run(
            ["git", "clone", source, str(dest)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

    def _mount_local(self, source: str, dest: Path) -> None:
        """Mount collection via filesystem copy.

        Args:
            source: Source directory path
            dest: Destination directory

        Raises:
            FileNotFoundError: If source does not exist
            RuntimeError: If copy fails
        """
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Source directory not found: {source}")

        if not source_path.is_dir():
            raise ValueError(f"Source is not a directory: {source}")

        shutil.copytree(source_path, dest, dirs_exist_ok=True)

    def _get_git_cache_dir(self, identifier: str) -> Path:
        """Get cache directory for a collection.

        Args:
            identifier: Collection identifier

        Returns:
            Path to collection cache directory
        """
        return self.git_cache_dir / identifier

    def _clone_to_cache(self, identifier: str, source: str) -> Path:
        """Clone git repository or resolve local source to cache directory.

        Handles two source types:
        - git+: Clones repository to cache directory
        - path: Returns path as-is (no caching needed)

        Args:
            identifier: Collection identifier
            source: Collection source (git+, or path)

        Returns:
            Path to collection directory

        Raises:
            ValueError: If source format is unknown
            RuntimeError: If git clone fails
            FileNotFoundError: If local path doesn't exist
        """
        # Handle local collections - return path as-is
        if not source.startswith("git+"):
            local_path = Path(source)
            if not local_path.exists():
                raise FileNotFoundError(f"Local collection not found: {local_path}")
            logger.info(f"Using local collection at {local_path}")
            return local_path

        # Git collections - proceed with existing clone logic below
        git_cache_dir = self._get_git_cache_dir(identifier)

        if git_cache_dir.exists():
            logger.info(f"Collection {identifier} already cached at {git_cache_dir}")
            return git_cache_dir

        git_url = source[4:]
        if "#subdirectory=" in git_url:
            git_url, subdir_part = git_url.split("#subdirectory=", 1)
            subdirectory = subdir_part
        elif "#" in git_url:
            git_url, subdirectory = git_url.split("#", 1)
        else:
            subdirectory = None

        # Extract branch if present
        if "@" in git_url:
            url_part, branch_part = git_url.rsplit("@", 1)
            git_url = url_part
            branch = branch_part
        else:
            branch = None

        # Clone to temporary location if subdirectory specified, otherwise directly to cache
        temp_clone: Path | None = None
        if subdirectory:
            temp_clone = git_cache_dir.parent / f".temp_{identifier}"
            clone_target = temp_clone
        else:
            clone_target = git_cache_dir

        logger.info(
            f"Cloning {identifier} from {git_url} "
            f"(branch: {branch or 'default'}, subdir: {subdirectory or 'root'}) "
            f"to cache: {git_cache_dir}"
        )

        cmd = ["git", "clone"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([git_url, str(clone_target)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        # If subdirectory specified, move it to cache_dir
        if subdirectory and temp_clone:
            source_subdir = temp_clone / subdirectory
            if not source_subdir.exists():
                shutil.rmtree(temp_clone, ignore_errors=True)
                raise RuntimeError(f"Subdirectory '{subdirectory}' not found in repository")

            shutil.move(str(source_subdir), str(git_cache_dir))
            shutil.rmtree(temp_clone, ignore_errors=True)
            logger.info(f"Extracted subdirectory '{subdirectory}' to cache")

        logger.info(f"Successfully cloned {identifier} to cache")
        return git_cache_dir

    def _reload_collections_from_disk(self) -> None:
        """Reload collections from disk into memory.

        This is used by sync_collections to pick up any manual edits to collections.yaml.
        """
        self._load_registry()

    def sync_collections(self, update: bool = False) -> dict[str, str]:
        """Sync all collections from registry.

        Args:
            update: If True, run git pull for cached git repos

        Returns:
            Dictionary mapping collection name to status ("synced", "updated", "skipped", "error")
        """
        # Reload from disk to pick up any manual edits to collections.yaml
        self._reload_collections_from_disk()

        results = {}

        for name, entry in self._collections.items():
            source = entry.source
            if not source:
                logger.info(f"Collection {name} has no source, skipping")
                results[name] = "skipped"
                continue

            try:
                is_git_source = source.startswith("git+")

                if is_git_source:
                    git_cache_dir = self._get_git_cache_dir(name)
                    if not git_cache_dir.exists():
                        logger.info(f"Cloning {name} to cache")
                        git_cache_dir = self._clone_to_cache(name, source)
                        results[name] = "synced"
                    elif update:
                        shutil.rmtree(git_cache_dir)
                        logger.info(f"Re-cloning {name} to cache")
                        git_cache_dir = self._clone_to_cache(name, source)
                        results[name] = "synced"
                    else:
                        results[name] = "skipped"

                    source_dir = git_cache_dir
                else:
                    local_path = Path(source)
                    if not local_path.exists():
                        logger.warning(f"Local collection path does not exist: {local_path}")
                        results[name] = "error"
                        continue
                    source_dir = local_path
                    results[name] = "synced"

                if self.discovery_service and results.get(name) in [
                    "synced",
                    "updated",
                ]:
                    try:
                        logger.info(f"Auto-discovering profiles from collection: {name}")
                        discovered_profiles = self.discovery_service.discover_profiles(name, source_dir)
                        logger.info(f"Discovered {len(discovered_profiles)} profiles from {name}")

                        # Auto-compile profiles if compilation service available
                        if self.compilation_service and discovered_profiles:
                            compiled_count = 0
                            for profile in discovered_profiles:
                                try:
                                    compiled_path = self.compilation_service.compile_profile(name, profile)
                                    logger.info(f"Auto-compiled profile: {name}/{profile.name} → {compiled_path}")
                                    compiled_count += 1
                                except Exception as e:
                                    logger.warning(f"Failed to auto-compile {name}/{profile.name}: {e}")

                            logger.info(
                                f"Auto-compiled {compiled_count}/{len(discovered_profiles)} profiles from {name}"
                            )

                    except Exception as e:
                        logger.warning(f"Failed to auto-discover profiles from {name}: {e}")

            except Exception as e:
                logger.error(f"Error syncing collection {name}: {e}")
                results[name] = "error"

        logger.info(f"Collection sync complete: {results}")
        return results
