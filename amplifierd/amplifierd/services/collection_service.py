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
from amplifierd.models.collections import ComponentRefsResponse


@dataclass
class MountResult:
    """Result of mounting a collection."""

    success: bool
    collection_id: str
    profile_count: int
    message: str
    warning: str | None = None


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
            f"CollectionService initialized with share_dir={self.share_dir}, state_dir={self.state_dir}{services_str}"
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
        """List all collections from registry plus local collection if it exists.

        Returns:
            List of CollectionInfo objects including:
            - All collections from registry
            - Local collection if it has profiles
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

        # Check if local collection exists and has profiles
        local_collection_dir = self.collections_cache_dir / "local"
        if local_collection_dir.exists():
            # Count profiles (directories with profile.md files)
            profile_count = sum(1 for p in local_collection_dir.iterdir() if p.is_dir() and (p / "profile.md").exists())

            # Add local collection if not already in registry and has profiles
            if profile_count > 0 and "local" not in self._collections:
                logger.info(f"Found local collection with {profile_count} profiles")
                collections.append(
                    CollectionInfo(
                        identifier="local",
                        source="local",
                        profiles=[],
                    )
                )

        logger.info(f"Found {len(collections)} collections (including local if present)")
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

    def mount_collection(self, identifier: str, source: str) -> MountResult:
        """Mount a collection from a source and sync profiles.

        Source can be:
        - git+URL: Clones repository to cache
        - /path/to/dir: Uses local filesystem path

        Args:
            identifier: Collection identifier (directory name)
            source: Git URL (git+...) or local filesystem path

        Returns:
            MountResult with success status, profile count, and any warnings

        Raises:
            ValueError: If collection already exists
            RuntimeError: If mounting fails
        """
        if self.get_collection(identifier):
            raise ValueError(f"Collection already exists: {identifier}")

        try:
            # Clone or validate source
            if source.startswith("git+"):
                # Clone/cache the git repository
                collection_path = self._clone_to_cache(identifier, source)
            else:
                # Local filesystem path - validate it exists
                source_path = Path(source)
                if not source_path.exists():
                    raise FileNotFoundError(f"Source directory not found: {source}")
                if not source_path.is_dir():
                    raise ValueError(f"Source is not a directory: {source}")
                collection_path = source_path

            # Add to registry
            self._add_collection_to_registry(
                name=identifier,
                source=source,
            )

            logger.info(f"Successfully mounted collection {identifier} from {source}")

            # Sync profiles
            profile_count, errors = self._sync_collection_profiles(identifier, collection_path)

            if errors:
                warning = f"Some profiles failed to compile: {'; '.join(errors)}"
                return MountResult(
                    success=True,
                    collection_id=identifier,
                    profile_count=profile_count,
                    message=f"Collection mounted with {profile_count} profile(s)",
                    warning=warning,
                )

            return MountResult(
                success=True,
                collection_id=identifier,
                profile_count=profile_count,
                message=f"Collection mounted successfully with {profile_count} profile(s)",
            )

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

    def _sync_collection_profiles(
        self, collection_id: str, collection_path: Path, force_compile: bool = False
    ) -> tuple[int, list[str]]:
        """Discover and compile profiles for a collection.

        Args:
            collection_id: Collection identifier
            collection_path: Path to collection directory
            force_compile: If True, force profile recompilation even if up-to-date

        Returns:
            (profile_count, errors) where errors is list of error messages
        """
        errors = []
        profile_count = 0

        if not self.discovery_service:
            return 0, ["Profile discovery service not available"]

        try:
            logger.info(f"Auto-discovering profiles from collection: {collection_id}")
            discovered_profiles = self.discovery_service.discover_profiles(collection_id, collection_path)
            logger.info(f"Discovered {len(discovered_profiles)} profiles from {collection_id}")

            # Auto-compile profiles if compilation service available
            if self.compilation_service and discovered_profiles:
                for profile in discovered_profiles:
                    try:
                        compiled_path = self.compilation_service.compile_profile(
                            collection_id, profile, force=force_compile
                        )
                        logger.info(f"Auto-compiled profile: {collection_id}/{profile.name} → {compiled_path}")
                        profile_count += 1
                    except Exception as e:
                        error_msg = f"Failed to compile {collection_id}/{profile.name}: {e}"
                        logger.warning(error_msg)
                        errors.append(error_msg)

                logger.info(f"Auto-compiled {profile_count}/{len(discovered_profiles)} profiles from {collection_id}")
            else:
                # Discovery succeeded but no compilation service
                profile_count = len(discovered_profiles)

        except Exception as e:
            error_msg = f"Failed to discover profiles from {collection_id}: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)

        return profile_count, errors

    def sync_collections(
        self,
        force_refresh: bool = False,
        auto_compile: bool = True,
        force_compile: bool = False,
    ) -> dict[str, str]:
        """Sync all collections from registry.

        Args:
            force_refresh: If True, delete cached git repos and re-clone (formerly 'update')
            auto_compile: If True, automatically compile profiles after sync
            force_compile: If True, force profile recompilation even if up-to-date

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
                    elif force_refresh:
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

                if auto_compile and results.get(name) in ["synced", "updated"]:
                    self._sync_collection_profiles(name, source_dir, force_compile=force_compile)

            except Exception as e:
                logger.error(f"Error syncing collection {name}: {e}")
                results[name] = "error"

        logger.info(f"Collection sync complete: {results}")
        return results

    def get_all_component_refs(self) -> ComponentRefsResponse:
        """Get all component references used across all profiles.

        Returns:
            ComponentRefsResponse with all component refs organized by type,
            sorted by profile identifier
        """
        from amplifierd.models.collections import ComponentRef
        from amplifierd.models.collections import ComponentRefsResponse

        # Initialize lists for each component type
        refs = {
            "orchestrators": [],
            "context_managers": [],
            "providers": [],
            "tools": [],
            "hooks": [],
            "agents": [],
            "contexts": [],
        }

        # Process all collections (including local)
        collections_to_process = []

        # Add registered collections
        for name in self._collections:
            collections_to_process.append((name, self.collections_cache_dir / name))

        # Add local collection if it exists
        local_dir = self.collections_cache_dir / "local"
        if local_dir.exists() and "local" not in self._collections:
            collections_to_process.append(("local", local_dir))

        # Process each collection
        for collection_id, collection_dir in collections_to_process:
            if not collection_dir.exists():
                continue

            # Find all profile directories (have profile.md or {name}.md)
            for profile_dir in collection_dir.iterdir():
                if not profile_dir.is_dir():
                    continue

                profile_id = profile_dir.name

                # Try standard naming first: profile.md
                profile_file = profile_dir / "profile.md"

                # Fall back to profile-name.md (e.g., dev.md in dev/ directory)
                if not profile_file.exists():
                    profile_file = profile_dir / f"{profile_id}.md"

                if not profile_file.exists():
                    continue

                profile_identifier = f"{collection_id}/{profile_id}"

                # Parse profile and extract component refs
                try:
                    # Parse YAML frontmatter manually
                    import yaml

                    content = profile_file.read_text(encoding="utf-8")

                    # Check for YAML frontmatter
                    if not content.startswith("---"):
                        continue

                    # Split frontmatter
                    parts = content.split("---", 2)
                    if len(parts) < 3:
                        continue

                    yaml_content = parts[1]

                    # Parse YAML
                    try:
                        data = yaml.safe_load(yaml_content)
                    except yaml.YAMLError:
                        continue

                    if not isinstance(data, dict):
                        continue

                    # Extract orchestrator (schema v2)
                    session = data.get("session", {})
                    if (orchestrator := session.get("orchestrator", {})) and (source := orchestrator.get("source")):
                        name = orchestrator.get("module", "orchestrator")
                        refs["orchestrators"].append(ComponentRef(profile=profile_identifier, name=name, uri=source))

                    # Extract context manager (schema v2)
                    if (context_manager := session.get("context_manager", {})) and (
                        source := context_manager.get("source")
                    ):
                        name = context_manager.get("module", "context-manager")
                        refs["context_managers"].append(ComponentRef(profile=profile_identifier, name=name, uri=source))

                    # Extract providers
                    for provider in data.get("providers", []):
                        if isinstance(provider, dict) and (source := provider.get("source")):
                            name = provider.get("module", "provider")
                            refs["providers"].append(ComponentRef(profile=profile_identifier, name=name, uri=source))

                    # Extract tools
                    for tool in data.get("tools", []):
                        if isinstance(tool, dict) and (source := tool.get("source")):
                            name = tool.get("module", "tool")
                            refs["tools"].append(ComponentRef(profile=profile_identifier, name=name, uri=source))

                    # Extract hooks
                    for hook in data.get("hooks", []):
                        if isinstance(hook, dict) and (source := hook.get("source")):
                            name = hook.get("module", "hook")
                            refs["hooks"].append(ComponentRef(profile=profile_identifier, name=name, uri=source))

                    # Extract agents (dict format only: {name: uri})
                    agents_data = data.get("agents", {})
                    if not isinstance(agents_data, dict):
                        logger.error(
                            f"Invalid agents format in {profile_identifier}: "
                            f"expected dict {{name: uri}}, got {type(agents_data).__name__}. "
                            "See docs/01-concepts/profiles.md for correct format."
                        )
                        agents_data = {}

                    for agent_name, agent_uri in agents_data.items():
                        if isinstance(agent_uri, str):
                            refs["agents"].append(
                                ComponentRef(profile=profile_identifier, name=agent_name, uri=agent_uri)
                            )

                    # Extract contexts (dict format only: {name: uri})
                    contexts_data = data.get("context", {})
                    if not isinstance(contexts_data, dict):
                        logger.error(
                            f"Invalid context format in {profile_identifier}: "
                            f"expected dict {{name: uri}}, got {type(contexts_data).__name__}. "
                            "See docs/01-concepts/profiles.md for correct format."
                        )
                        contexts_data = {}

                    for context_name, context_uri in contexts_data.items():
                        if isinstance(context_uri, str):
                            refs["contexts"].append(
                                ComponentRef(profile=profile_identifier, name=context_name, uri=context_uri)
                            )

                except Exception as e:
                    logger.warning(f"Failed to parse profile {profile_identifier}: {e}")
                    continue

        # Sort each list by profile identifier
        for component_type in refs:
            refs[component_type].sort(key=lambda x: x.profile)

        return ComponentRefsResponse(
            orchestrators=refs["orchestrators"],
            context_managers=refs["context_managers"],
            providers=refs["providers"],
            tools=refs["tools"],
            hooks=refs["hooks"],
            agents=refs["agents"],
            contexts=refs["contexts"],
        )
