"""Profile discovery service for scanning and caching profile manifests."""

import logging
import shutil
from pathlib import Path

import yaml
from pydantic import ValidationError

from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.utils.profile_validation import is_valid_profile

logger = logging.getLogger(__name__)


class ProfileValidationError(Exception):
    """Raised when profile fails validation."""


class ProfileDiscoveryService:
    """
    Discovers profiles from collection sources.

    Scans collection directories for schema v2 profiles and caches manifests.
    Only profiles with schema_version: 2 are accepted. Schema v1 profiles
    and profiles with missing or invalid schema versions are rejected with
    clear logging.

    The service performs three main operations:
    1. Scan: Find profile files in collection directories
    2. Parse: Extract and validate YAML frontmatter
    3. Cache: Store valid profile manifests for later use

    Profile files must follow this structure:
        ---
        profile:
          name: myprofile
          schema_version: 2
          version: 1.0.0
          description: "Profile description"
        session:
          orchestrator:
            module: loop-streaming
            source: git+https://github.com/...
        tools: [...]
        ---

        # Profile markdown content
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize with profile cache directory.

        Args:
            cache_dir: Path to share/profiles/ where profile manifests
                      are cached, organized by collection ID
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def discover_profiles(self, collection_id: str, collection_path: Path) -> list[ProfileDetails]:
        """
        Scan collection for schema v2 profiles.

        Recursively scans the collection's profiles/ directory for .md files,
        validates them as schema v2 profiles, and caches valid manifests.

        Args:
            collection_id: Collection identifier (used for cache organization)
            collection_path: Path to collection root directory

        Returns:
            List of valid ProfileDetails objects (only schema v2 profiles)

        Side Effects:
            Writes manifests to cache_dir/{collection_id}/*.md
            Logs warnings for rejected profiles (schema v1, invalid, etc.)

        Example:
            >>> service = ProfileDiscoveryService(Path("/cache/profiles"))
            >>> profiles = service.discover_profiles(
            ...     "my-collection",
            ...     Path("/collections/my-collection")
            ... )
            >>> print(f"Found {len(profiles)} valid profiles")
        """
        profile_files = self._scan_profiles(collection_path)

        if not profile_files:
            logger.info(f"No profile files found in collection '{collection_id}' at {collection_path}")
            return []

        logger.info(f"Found {len(profile_files)} profile files in collection '{collection_id}'")

        valid_profiles: list[ProfileDetails] = []

        for profile_file in profile_files:
            try:
                manifest: ProfileDetails | None = self._parse_profile_manifest(profile_file)

                if manifest is None:
                    continue

                # Cache the valid profile
                self._cache_profile(collection_id, profile_file, manifest)
                valid_profiles.append(manifest)

            except Exception as e:
                logger.error(
                    f"Unexpected error processing {profile_file.name}: {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"Cached {len(valid_profiles)} valid profiles from collection '{collection_id}'")

        return valid_profiles

    def get_cached_profile(self, collection_id: str, profile_id: str) -> ProfileDetails | None:
        """
        Get profile manifest from cache.

        Reads a previously cached profile manifest and returns its parsed details.

        Args:
            collection_id: Collection identifier
            profile_id: Profile identifier (profile name)

        Returns:
            ProfileDetails if cached, None if not found or invalid

        Example:
            >>> profile = service.get_cached_profile("my-collection", "base")
            >>> if profile:
            ...     print(f"Profile: {profile.name} v{profile.version}")
        """
        # Updated path: includes nested profile_id directory
        cache_file = self.cache_dir / collection_id / profile_id / f"{profile_id}.md"

        if not cache_file.exists():
            logger.debug(f"Profile {collection_id}/{profile_id} not found in cache at {cache_file}")
            return None

        try:
            manifest = self._parse_profile_manifest(cache_file)
            if manifest:
                return manifest

            logger.warning(f"Cached profile {collection_id}/{profile_id} is invalid, returning None")
            return None

        except Exception as e:
            logger.error(
                f"Error reading cached profile {collection_id}/{profile_id}: {e}",
                exc_info=True,
            )
            return None

    def list_cached_profiles(self, collection_id: str | None = None) -> list[ProfileDetails]:
        """
        List all cached profiles.

        Optionally filter by collection ID to get profiles from a specific collection.

        Args:
            collection_id: Optional filter by collection. If None, returns
                          profiles from all collections.

        Returns:
            List of ProfileDetails objects from cache

        Example:
            >>> # Get all cached profiles
            >>> all_profiles = service.list_cached_profiles()
            >>>
            >>> # Get profiles from specific collection
            >>> my_profiles = service.list_cached_profiles("my-collection")
        """
        cached_profiles: list[ProfileDetails] = []

        if collection_id:
            # Search specific collection
            collection_cache_dir = self.cache_dir / collection_id
            if collection_cache_dir.exists():
                profile_files = list(collection_cache_dir.glob("*.md"))
            else:
                profile_files = []
        else:
            # Search all collections
            profile_files = list(self.cache_dir.glob("*/*.md"))

        for profile_file in profile_files:
            try:
                manifest = self._parse_profile_manifest(profile_file)
                if manifest:
                    cached_profiles.append(manifest)
            except Exception as e:
                logger.error(f"Error reading cached profile {profile_file}: {e}", exc_info=True)
                continue

        return cached_profiles

    def _scan_profiles(self, collection_path: Path) -> list[Path]:
        """
        Find all profile files in collection.

        Scans the collection root directory for .md files with valid profile manifests.
        Per spec: profiles are at collection root (*.md), not in subdirectories.

        Args:
            collection_path: Path to collection root

        Returns:
            List of paths to profile .md files

        Note:
            Looks for *.md files at collection root (not in subdirectories).
            This matches the spec requirement for both git and fsspec collections.
        """
        if not collection_path.exists():
            logger.debug(f"Collection path does not exist: {collection_path}")
            return []

        if not collection_path.is_dir():
            logger.warning(f"Collection path is not a directory: {collection_path}")
            return []

        # Scan for .md files at collection root (not recursive)
        profile_files = list(collection_path.glob("*.md"))

        # Filter out README and other non-profile markdown files
        # Profile files must have YAML frontmatter starting with '---'
        valid_profiles = []
        for profile_file in profile_files:
            if is_valid_profile(profile_file):
                valid_profiles.append(profile_file)
            else:
                logger.debug(f"Skipping non-profile markdown file: {profile_file.name}")

        logger.debug(f"Found {len(valid_profiles)} profile files (with YAML frontmatter) in {collection_path}")

        return valid_profiles

    def _parse_profile_manifest(self, profile_file: Path) -> ProfileDetails | None:
        """
        Parse profile YAML frontmatter.

        Extracts and validates YAML frontmatter from profile markdown files.
        Only accepts profiles with schema_version: 2. Rejects schema v1 or
        profiles with missing/invalid schema versions.

        Args:
            profile_file: Path to profile .md file

        Returns:
            ProfileDetails if valid schema v2 profile, None otherwise

        Expected Format:
            ---
            profile:
              name: myprofile
              schema_version: 2
              version: 1.0.0
              description: "..."
            session:
              orchestrator:
                module: loop-streaming
                source: git+https://github.com/...
            tools:
              - module: tool-web
                source: git+https://github.com/...
            providers: [...]
            hooks: [...]
            ---

            # Markdown content

        Validation:
            - Must have schema_version: 2
            - Must have required fields (name, version, description)
            - Rejects schema v1 or missing schema version with warning
        """
        try:
            content = profile_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {profile_file}: {e}")
            return None

        # Check for YAML frontmatter
        if not content.startswith("---"):
            logger.warning(f"Skipping {profile_file.name}: No YAML frontmatter found (must start with '---')")
            return None

        # Split frontmatter from markdown content
        parts = content.split("---", 2)
        if len(parts) < 3:
            logger.warning(f"Skipping {profile_file.name}: Invalid frontmatter format (need closing '---')")
            return None

        yaml_content = parts[1]

        # Parse YAML
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML in {profile_file.name}: {e}")
            return None

        if not isinstance(data, dict):
            logger.warning(f"Skipping {profile_file.name}: Frontmatter must be a YAML dictionary")
            return None

        # Extract profile section
        profile_data = data.get("profile", {})
        if not profile_data:
            logger.warning(f"Skipping {profile_file.name}: No 'profile' section in frontmatter")
            return None

        # Validate schema version (CRITICAL: must be 2)
        schema_version = profile_data.get("schema_version")

        if schema_version is None:
            logger.warning(
                f"Skipping {profile_file.name}: Missing 'schema_version' in profile section. Schema v2 required."
            )
            return None

        if schema_version != 2:
            logger.warning(
                f"Skipping {profile_file.name}: "
                f"schema_version {schema_version} not supported. "
                "Only schema_version: 2 is accepted. "
                "Please update profile to schema v2."
            )
            return None

        # Build ProfileDetails from validated data
        try:
            # Extract required fields
            name = profile_data.get("name")
            version = profile_data.get("version")
            description = profile_data.get("description", "")

            if not name or not version:
                logger.warning(f"Skipping {profile_file.name}: Missing required fields (name, version)")
                return None

            # Extract optional module lists
            providers_data = data.get("providers", [])
            tools_data = data.get("tools", [])
            hooks_data = data.get("hooks", [])

            # Parse module configs
            providers = [ModuleConfig(**p) for p in providers_data]
            tools = [ModuleConfig(**t) for t in tools_data]
            hooks = [ModuleConfig(**h) for h in hooks_data]

            # Parse session config (schema v2)
            session_data = data.get("session")
            session_config = None

            if session_data:
                # Extract orchestrator (required)
                orchestrator_data = session_data.get("orchestrator")
                if not orchestrator_data:
                    logger.warning(
                        f"Skipping {profile_file.name}: Schema v2 profile missing required session.orchestrator"
                    )
                    return None

                # Parse orchestrator
                try:
                    orchestrator = ModuleConfig(**orchestrator_data)
                except Exception as e:
                    logger.error(f"Failed to parse orchestrator config in {profile_file.name}: {e}")
                    return None

                # Parse context-manager (optional)
                context_manager = None
                context_manager_data = session_data.get("context-manager") or session_data.get("context_manager")
                if context_manager_data:
                    try:
                        context_manager = ModuleConfig(**context_manager_data)
                    except Exception as e:
                        logger.warning(f"Failed to parse context-manager in {profile_file.name}: {e}")

                # Create SessionConfig
                from amplifierd.models.profiles import SessionConfig

                session_config = SessionConfig(
                    orchestrator=orchestrator,
                    context_manager=context_manager,
                )

            # Extract agent and context refs (schema v2)
            # These can be either lists (simple refs) or dicts (named refs)
            agents_data = data.get("agents", [])
            context_data = data.get("context", [])

            # Convert dict format {name: url} to list of urls
            if isinstance(agents_data, dict):
                agents_data = list(agents_data.values())
            elif not isinstance(agents_data, list):
                logger.warning(f"Invalid agents field in {profile_file.name}: expected list or dict")
                agents_data = []

            if isinstance(context_data, dict):
                context_data = list(context_data.values())
            elif not isinstance(context_data, list):
                logger.warning(f"Invalid context field in {profile_file.name}: expected list or dict")
                context_data = []

            # Create ProfileDetails
            manifest = ProfileDetails(
                name=name,
                schema_version=schema_version,
                version=version,
                description=description,
                collection_id=None,  # Set by caller if needed
                source="collection",  # Profiles discovered from collections
                is_active=False,  # Activation status set elsewhere
                providers=providers,
                tools=tools,
                hooks=hooks,
                session=session_config,
                agents=agents_data,
                context=context_data,
            )

            logger.debug(f"Successfully parsed {profile_file.name}: {manifest.name} v{manifest.version}")

            return manifest

        except ValidationError as e:
            logger.error(f"Failed to validate profile {profile_file.name} against model: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error building ProfileDetails for {profile_file.name}: {e}",
                exc_info=True,
            )
            return None

    def _cache_profile(self, collection_id: str, profile_file: Path, manifest: ProfileDetails) -> None:
        """
        Write profile manifest to cache.

        Copies the entire profile file (frontmatter + markdown content) to the
        cache directory organized by collection ID and profile ID.

        Args:
            collection_id: Collection identifier (for cache organization)
            profile_file: Original profile file path
            manifest: Parsed ProfileDetails (for logging)

        Side Effects:
            Writes to cache_dir/{collection_id}/{profile_id}/{profile_id}.md
            Creates collection and profile directories if needed

        Note:
            Copies entire file, not just frontmatter, so markdown content
            is preserved for potential future use.
        """
        # Create collection cache directory
        cache_collection_dir = self.cache_dir / collection_id
        cache_collection_dir.mkdir(parents=True, exist_ok=True)

        # Create nested profile directory (spec requirement)
        profile_cache_dir = cache_collection_dir / manifest.name
        profile_cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache file uses profile name
        cache_file = profile_cache_dir / f"{manifest.name}.md"

        try:
            # Copy entire profile file (frontmatter + content)
            shutil.copy2(profile_file, cache_file)
            logger.info(f"Cached profile: {collection_id}/{manifest.name} v{manifest.version} to {cache_file}")
        except Exception as e:
            logger.error(
                f"Failed to cache profile {collection_id}/{manifest.name}: {e}",
                exc_info=True,
            )
            raise ProfileValidationError(f"Failed to cache profile {manifest.name}: {e}")
