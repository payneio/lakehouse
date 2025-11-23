"""Simple collection management service.

Lists collections from registry, mounts via git clone or filesystem copy,
and unmounts via directory removal.
"""

import logging
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

import yaml

from amplifier_library.storage import get_state_dir
from amplifierd.models.collections import CollectionDetails
from amplifierd.models.collections import CollectionInfo
from amplifierd.models.collections import CollectionModules

from .collection_registry import CollectionRegistry
from .collection_registry import CollectionResourceInfo

logger = logging.getLogger(__name__)


class SimpleCollectionService:
    """Simple collection management service.

    Manages collections using Unix-style flat layout:
    - Tracks installations in collections.yaml registry
    - Extracts resources to type-based directories (modules/, profiles/, etc.)
    - Each resource is namespaced by collection name
    """

    def __init__(self, share_dir: Path) -> None:
        """Initialize collection service.

        Args:
            share_dir: Root share directory for resources
        """
        self.share_dir = Path(share_dir)
        self.share_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir = get_state_dir()
        self.collections_cache_dir = self.state_dir / "collections"
        self.collections_cache_dir.mkdir(parents=True, exist_ok=True)
        self.registry = CollectionRegistry(share_dir)

        self.registry.initialize_with_defaults()

        logger.info(f"SimpleCollectionService initialized with share_dir={self.share_dir}, state_dir={self.state_dir}")

    def list_collections(self) -> list[CollectionInfo]:
        """List all collections from registry.

        Returns:
            List of CollectionInfo objects
        """
        collections = []

        for name, entry in self.registry.list_collections():
            if entry.source.startswith(("git+", "https://", "git@")):
                collection_type = "git"
            elif entry.source.startswith("bundled:"):
                collection_type = "bundled"
            else:
                collection_type = "local"

            collections.append(
                CollectionInfo(
                    identifier=name,
                    source=entry.source,
                    type=collection_type,
                    package_bundled=entry.package_bundled,
                )
            )

        logger.info(f"Found {len(collections)} collections")
        return collections

    def get_collection(self, identifier: str) -> CollectionDetails:
        """Get detailed information about a collection.

        Args:
            identifier: Collection identifier

        Returns:
            CollectionDetails object

        Raises:
            FileNotFoundError: If collection does not exist
        """
        entry = self.registry.get_collection(identifier)
        if not entry:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        if entry.source.startswith(("git+", "https://", "git@")):
            collection_type = "git"
        elif entry.source.startswith("bundled:"):
            collection_type = "bundled"
        else:
            collection_type = "local"

        return CollectionDetails(
            identifier=identifier,
            source=entry.source,
            type=collection_type,
            profiles=entry.resources.profiles,
            agents=entry.resources.agents,
            modules=CollectionModules(
                providers=entry.resources.modules,
                tools=entry.resources.modules,
                hooks=entry.resources.modules,
                orchestrators=entry.resources.modules,
            ),
            package_bundled=entry.package_bundled,
        )

    def mount_collection(self, identifier: str, source: str, method: str = "git") -> None:
        """Mount a collection from a source.

        For git sources, clones to state cache directory then extracts to share directories.
        For local sources, copies directly to share directories.

        Args:
            identifier: Collection identifier (directory name)
            source: Source URL (git) or path (local)
            method: Mount method ("git" or "local")

        Raises:
            ValueError: If method is invalid or collection already exists
            RuntimeError: If mounting fails
        """
        if self.registry.get_collection(identifier):
            raise ValueError(f"Collection already exists: {identifier}")

        if method not in ["git", "local"]:
            raise ValueError(f"Invalid mount method: {method}. Must be 'git' or 'local'")

        temp_dir = None
        try:
            if method == "git":
                cache_dir = self._clone_to_cache(identifier, source)
                source_dir = cache_dir
            else:
                temp_dir = Path(tempfile.mkdtemp())
                self._mount_local(source, temp_dir)
                source_dir = temp_dir

            # Try collection.yaml first
            collection_yaml = source_dir / "collection.yaml"
            if collection_yaml.exists():
                with open(collection_yaml) as f:
                    manifest = yaml.safe_load(f)
                version = manifest.get("version", "0.0.0") if manifest else "0.0.0"
            # Fallback to pyproject.toml
            elif (pyproject := source_dir / "pyproject.toml").exists():
                with open(pyproject, "rb") as f:
                    pyproject_data = tomllib.load(f)
                version = pyproject_data.get("project", {}).get("version", "0.0.0")
            else:
                raise RuntimeError("Source does not contain collection.yaml or pyproject.toml")

            installed_resources = self._extract_resources(identifier, source_dir)

            self.registry.add_collection(name=identifier, source=source, version=version, resources=installed_resources)

            logger.info(f"Successfully mounted collection {identifier} from {source}")

        except Exception as e:
            self._rollback_resources(identifier)
            raise RuntimeError(f"Failed to mount collection {identifier}: {e}")

        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)

    def unmount_collection(self, identifier: str) -> None:
        """Unmount a collection.

        Args:
            identifier: Collection identifier

        Raises:
            FileNotFoundError: If collection does not exist
        """
        resources = self.registry.remove_collection(identifier)
        if not resources:
            raise FileNotFoundError(f"Collection not found: {identifier}")

        self._remove_resources(identifier, resources)
        logger.info(f"Successfully unmounted collection {identifier}")

    def _extract_resources(self, identifier: str, source_dir: Path) -> CollectionResourceInfo:
        """Extract resources with metadata parsing.

        Args:
            identifier: Collection identifier
            source_dir: Temporary directory containing collection source

        Returns:
            CollectionResourceInfo with extracted resource paths
        """
        installed = CollectionResourceInfo(modules=[], profiles=[], agents=[], context=[])

        # Extract modules first (needed for namespace)
        if (source_dir / "modules").exists():
            installed.modules = self._extract_modules(source_dir / "modules", identifier)

        # Extract profiles
        if (source_dir / "profiles").exists():
            installed.profiles = self._extract_profiles(source_dir / "profiles", identifier)
            # Resolve profile module dependencies AFTER profiles extracted
            self._resolve_profile_dependencies(installed.profiles, identifier)

        # Extract agents and context (unchanged)
        if (source_dir / "agents").exists():
            installed.agents = self._extract_agents(source_dir / "agents", identifier)

        if (source_dir / "context").exists():
            installed.context = self._extract_context(source_dir / "context", identifier)

        return installed

    def _extract_modules(self, src: Path, collection: str) -> list[str]:
        """Extract modules to flat structure: modules/{collection}/{module-name}/

        Args:
            src: Source modules directory
            collection: Collection name for namespace

        Returns:
            List of installed module paths
        """
        installed = []
        dest = self.share_dir / "modules" / collection
        dest.mkdir(parents=True, exist_ok=True)

        # Simple flat copy - one directory per module
        for module_dir in src.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith((".", "_")):
                continue

            module_name = module_dir.name
            dest_module = dest / module_name
            shutil.copytree(module_dir, dest_module, dirs_exist_ok=True)

            module_path = f"modules/{collection}/{module_name}"
            installed.append(module_path)

        return installed

    def _extract_profiles(self, src: Path, collection: str) -> list[str]:
        """Extract profiles and return only valid profile files.

        Validates that .md files have proper YAML frontmatter with profile.name and profile.version.

        Args:
            src: Source profiles directory
            collection: Collection name for namespace

        Returns:
            List of valid profile paths relative to share_dir
        """
        dest = self.share_dir / "profiles" / collection
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, dirs_exist_ok=True)

        valid_profiles = []

        # Check .md files for valid frontmatter
        for md_file in dest.rglob("*.md"):
            if self._is_valid_profile(md_file):
                valid_profiles.append(md_file)
            else:
                logger.debug(f"Skipping {md_file.name} - not a valid profile (missing profile.name or profile.version)")

        # Include .yaml files (assumed valid)
        valid_profiles.extend(dest.rglob("*.yaml"))

        return [str(p.relative_to(self.share_dir)) for p in valid_profiles]

    def _is_valid_profile(self, profile_path: Path) -> bool:
        """Check if file has valid profile frontmatter.

        Args:
            profile_path: Path to profile file

        Returns:
            True if file has profile.name and profile.version in frontmatter
        """
        try:
            with open(profile_path) as f:
                content = f.read()

            # Extract YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    data = yaml.safe_load(parts[1])
                else:
                    return False
            else:
                # Try parsing as pure YAML
                data = yaml.safe_load(content)

            # Validate required fields
            if not isinstance(data, dict):
                return False

            profile = data.get("profile", {})
            if not isinstance(profile, dict):
                return False

            # Check for required fields
            has_name = "name" in profile
            has_version = "version" in profile

            return has_name and has_version

        except Exception as e:
            logger.debug(f"Error validating {profile_path.name}: {e}")
            return False

    def _extract_agents(self, src: Path, collection: str) -> list[str]:
        """Extract agents and return paths.

        Args:
            src: Source agents directory
            collection: Collection name for namespace

        Returns:
            List of agent paths relative to share_dir
        """
        dest = self.share_dir / "agents" / collection
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return [str(p.relative_to(self.share_dir)) for p in dest.rglob("*.yaml")]

    def _extract_context(self, src: Path, collection: str) -> list[str]:
        """Extract context and return paths.

        Args:
            src: Source context directory
            collection: Collection name for namespace

        Returns:
            List of context paths relative to share_dir
        """
        dest = self.share_dir / "context" / collection
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, dirs_exist_ok=True)
        return [str(p.relative_to(self.share_dir)) for p in dest.rglob("*.md")]

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

    def _remove_resources(self, identifier: str, resources: CollectionResourceInfo) -> None:
        """Remove extracted resources for a collection.

        Args:
            identifier: Collection identifier
            resources: Resources to remove
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

    def _get_cache_dir(self, identifier: str) -> Path:
        """Get cache directory for a collection.

        Args:
            identifier: Collection identifier

        Returns:
            Path to collection cache directory
        """
        return self.collections_cache_dir / identifier

    def _resolve_bundled_source(self, source: str) -> Path:
        """Resolve bundled:module.path to filesystem path.

        Uses importlib.resources for portable package resource access.

        Args:
            source: Bundled source string (e.g., "bundled:amplifierd.data.collections.foundation")

        Returns:
            Path to the bundled collection directory

        Raises:
            ValueError: If module path is invalid or collection not found
            ModuleNotFoundError: If package doesn't exist
        """
        from importlib.resources import files

        try:
            module_path = source.removeprefix("bundled:")

            # Split into package and resource
            parts = module_path.split(".")
            if len(parts) < 2:
                raise ValueError(f"Invalid bundled source format: {source}\nExpected: bundled:package.module.resource")

            package = ".".join(parts[:-1])
            resource = parts[-1]

            # Resolve using importlib.resources
            resource_path = files(package) / resource
            resolved = Path(str(resource_path))

            # Verify it exists
            if not resolved.exists():
                raise FileNotFoundError(
                    f"Bundled collection directory not found: {module_path}\n"
                    f"Resolved to: {resolved}\n"
                    f"Ensure the collection is included in the package."
                )

            if not resolved.is_dir():
                raise ValueError(f"Bundled collection is not a directory: {module_path}\nResolved to: {resolved}")

            logger.info(f"Resolved bundled collection: {source} -> {resolved}")
            return resolved

        except ModuleNotFoundError as e:
            raise ValueError(
                f"Cannot resolve bundled collection: {source}\n"
                f"Module not found: {e.name}\n"
                f"Ensure the package is installed and collection path is correct."
            ) from e

    def _clone_to_cache(self, identifier: str, source: str) -> Path:
        """Clone git repository or resolve bundled/local source to cache directory.

        Handles three source types:
        - bundled: Resolves to package resource path (no caching needed)
        - git+: Clones repository to cache directory
        - local: Returns path as-is (no caching needed)

        Args:
            identifier: Collection identifier
            source: Collection source (bundled:, git+, or local: prefix)

        Returns:
            Path to collection directory

        Raises:
            ValueError: If source format is unknown or bundled collection not found
            RuntimeError: If git clone fails
            FileNotFoundError: If local path doesn't exist
        """
        # Handle bundled collections - resolve from package
        if source.startswith("bundled:"):
            return self._resolve_bundled_source(source)

        # Handle local collections - return path as-is
        if source.startswith("local:"):
            local_path = Path(source.removeprefix("local:"))
            if not local_path.exists():
                raise FileNotFoundError(f"Local collection not found: {local_path}")
            logger.info(f"Using local collection at {local_path}")
            return local_path

        # Git collections - proceed with existing clone logic below
        cache_dir = self._get_cache_dir(identifier)

        if cache_dir.exists():
            logger.info(f"Collection {identifier} already cached at {cache_dir}")
            return cache_dir

        # Parse source: git+URL[@branch][#subdirectory=path]
        git_url = source[4:] if source.startswith("git+") else source

        # Extract subdirectory if present
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
            temp_clone = cache_dir.parent / f".temp_{identifier}"
            clone_target = temp_clone
        else:
            clone_target = cache_dir

        logger.info(
            f"Cloning {identifier} from {git_url} "
            f"(branch: {branch or 'default'}, subdir: {subdirectory or 'root'}) "
            f"to cache: {cache_dir}"
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

            shutil.move(str(source_subdir), str(cache_dir))
            shutil.rmtree(temp_clone, ignore_errors=True)
            logger.info(f"Extracted subdirectory '{subdirectory}' to cache")

        logger.info(f"Successfully cloned {identifier} to cache")
        return cache_dir

    def _update_cache(self, identifier: str) -> None:
        """Update cached git repository with git pull.

        Args:
            identifier: Collection identifier

        Raises:
            RuntimeError: If git pull fails
        """
        cache_dir = self._get_cache_dir(identifier)

        if not cache_dir.exists():
            logger.warning(f"Cache directory does not exist for {identifier}")
            return

        if not (cache_dir / ".git").exists():
            logger.info(f"Not a git repository, skipping update: {cache_dir}")
            return

        logger.info(f"Updating cached collection {identifier} via git pull")
        result = subprocess.run(
            ["git", "pull"],
            cwd=cache_dir,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.warning(f"Git pull failed for {identifier}: {result.stderr}")
        else:
            logger.info(f"Successfully updated cache for {identifier}")

    def _load_collections_yaml(self) -> list[dict]:
        """Load declarative collections manifest.

        Expects format:
            collections:
              collection-name:
                source: "git+URL"
                method: "git"
                installed_at: "timestamp"
                version: "x.y.z"

        Returns:
            List of collection declarations with 'name' field added
        """
        manifest_file = self.share_dir / "collections.yaml"

        if not manifest_file.exists():
            logger.debug("No collections.yaml manifest found")
            return []

        try:
            with open(manifest_file) as f:
                data = yaml.safe_load(f)

            if not data or "collections" not in data:
                logger.warning("collections.yaml is empty or missing 'collections' key")
                return []

            collections_dict = data["collections"]
            if not isinstance(collections_dict, dict):
                logger.warning("collections.yaml 'collections' value is not a dictionary")
                return []

            # Convert dictionary format to list format for sync_collections
            collections_list = []
            for name, metadata in collections_dict.items():
                if not isinstance(metadata, dict):
                    logger.warning(f"Invalid metadata for collection {name}")
                    continue

                # Add name field and append to list
                collection_entry = {"name": name, **metadata}
                collections_list.append(collection_entry)

            logger.info(f"Loaded {len(collections_list)} collections from manifest")
            return collections_list

        except Exception as e:
            logger.error(f"Error loading collections.yaml: {e}")
            return []

    def _discover_package_collections(self) -> list[dict]:
        """Discover built-in collections from amplifierd package.

        Returns:
            List of collection specs for built-in collections
        """
        package_dir = Path(__file__).parent.parent
        collections_dir = package_dir / "data" / "collections"

        if not collections_dir.exists():
            logger.debug("No package collections directory found")
            return []

        discovered = []
        for dir_path in collections_dir.iterdir():
            if not dir_path.is_dir() or dir_path.name.startswith((".", "_")):
                continue

            has_resources = any((dir_path / subdir).is_dir() for subdir in ["modules", "profiles", "agents", "context"])

            if not has_resources:
                logger.warning(f"Skipping invalid package collection: {dir_path.name}")
                continue

            discovered.append(
                {
                    "name": dir_path.name,
                    "source": f"local:{dir_path}",
                    "method": "local",
                    "package_bundled": True,
                }
            )

        logger.info(f"Discovered {len(discovered)} package-bundled collection(s)")
        return discovered

    def sync_collections(self, update: bool = False) -> dict[str, str]:
        """Sync all collections: user-declared + package-bundled.

        Args:
            update: If True, run git pull for cached git repos

        Returns:
            Dictionary mapping collection name to status ("synced", "updated", "skipped", "error")
        """
        declared = self._load_collections_yaml()
        declared_ids = {coll.get("name") for coll in declared if coll.get("name")}

        package_collections = self._discover_package_collections()

        all_collections = declared.copy()
        for pkg_coll in package_collections:
            if pkg_coll["name"] not in declared_ids:
                all_collections.append(pkg_coll)
            else:
                logger.info(f"Skipping package collection '{pkg_coll['name']}' (user has explicit declaration)")

        results = {}

        for coll in all_collections:
            if not isinstance(coll, dict):
                logger.warning(f"Invalid collection entry: {coll}")
                continue

            name = coll.get("name")
            if not name:
                logger.warning("Collection missing name field")
                continue

            source = coll.get("source")
            if not source:
                logger.info(f"Collection {name} has no source, skipping")
                results[name] = "skipped"
                continue

            try:
                if source.startswith("package:"):
                    collection_name = source[8:]
                    package_dir = Path(__file__).parent.parent
                    resolved_path = package_dir / "data" / "collections" / collection_name
                    if resolved_path.exists():
                        source = f"local:{resolved_path}"
                        package_bundled = True
                    else:
                        logger.error(f"Package collection '{collection_name}' not found at {resolved_path}")
                        results[name] = "error"
                        continue
                else:
                    package_bundled = coll.get("package_bundled", False)

                is_git_source = source.startswith(("git+", "https://", "git@"))
                is_bundled_source = source.startswith("bundled:")
                is_local_source = source.startswith("local:")

                if is_bundled_source:
                    try:
                        source_dir = self._resolve_bundled_source(source)
                        results[name] = "synced"
                    except (ValueError, FileNotFoundError) as e:
                        logger.error(f"Failed to resolve bundled collection {name}: {e}")
                        results[name] = "error"
                        continue
                elif is_local_source or package_bundled:
                    local_path = Path(source.replace("local:", "", 1))
                    if not local_path.exists():
                        logger.warning(f"Local collection path does not exist: {local_path}")
                        results[name] = "error"
                        continue
                    source_dir = local_path
                    results[name] = "synced"
                else:
                    cache_dir = self._get_cache_dir(name)
                    if not cache_dir.exists():
                        if is_git_source:
                            logger.info(f"Cloning {name} to cache")
                            cache_dir = self._clone_to_cache(name, source)
                            results[name] = "synced"
                        else:
                            logger.warning(f"Collection {name} has unknown source format")
                            results[name] = "error"
                            continue
                    elif update and is_git_source and (cache_dir / ".git").exists():
                        logger.info(f"Updating {name} cache")
                        self._update_cache(name)
                        results[name] = "updated"
                    else:
                        results[name] = "skipped"
                    source_dir = cache_dir

                registry_entry = self.registry.get_collection(name)
                needs_extraction = (
                    not registry_entry
                    or not registry_entry.installed_at
                    or not any(
                        [
                            registry_entry.resources.modules,
                            registry_entry.resources.profiles,
                            registry_entry.resources.agents,
                            registry_entry.resources.context,
                        ]
                    )
                )

                if needs_extraction:
                    logger.info(f"Extracting {name} from source to share directories")

                    collection_yaml = source_dir / "collection.yaml"
                    pyproject_toml = source_dir / "pyproject.toml"

                    if collection_yaml.exists():
                        with open(collection_yaml) as f:
                            manifest = yaml.safe_load(f)
                        version = manifest.get("version", "0.0.0") if manifest else "0.0.0"
                    elif pyproject_toml.exists():
                        logger.info("No collection.yaml, reading from pyproject.toml")
                        with open(pyproject_toml, "rb") as f:
                            pyproject = tomllib.load(f)
                        version = pyproject.get("project", {}).get("version", "0.0.0")
                    else:
                        logger.warning(f"No collection.yaml or pyproject.toml in {name}, using defaults")
                        version = coll.get("version", "0.0.0")

                    installed_resources = self._extract_resources(name, source_dir)
                    self.registry.add_collection(
                        name=name,
                        source=source,
                        version=version,
                        resources=installed_resources,
                        package_bundled=package_bundled,
                    )
                    logger.info(f"Registered {name} in collections registry")

            except Exception as e:
                logger.error(f"Error syncing collection {name}: {e}")
                results[name] = "error"

        logger.info(f"Collection sync complete: {results}")
        return results
