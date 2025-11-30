"""Simple profile management service.

Scans flat profiles directory for profiles, handles one-level inheritance,
and manages active profile state in a simple text file.

Can optionally integrate with ProfileDiscoveryService and ProfileCompilationService
for schema v2 profile support.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from amplifierd.services.profile_compilation import ProfileCompilationService
    from amplifierd.services.profile_discovery import ProfileDiscoveryService

from amplifierd.models.profiles import CreateProfileRequest
from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.models.profiles import ProfileInfo
from amplifierd.models.profiles import SessionConfig
from amplifierd.models.profiles import UpdateProfileRequest

logger = logging.getLogger(__name__)


def _get_collection_from_source(source: str) -> str | None:
    """Extract collection name from profile source.

    Args:
        source: Profile source string (e.g., "max-payne-collection/profiles/default.yaml")

    Returns:
        Collection name or None
    """
    parts = source.split("/")
    if len(parts) >= 2 and parts[1] == "profiles":
        return parts[0]
    return None


@dataclass
class ProfileData:
    """Internal representation of profile data."""

    name: str
    version: str
    description: str
    schema_version: int = 2
    extends: str | None = None
    providers: list[dict[str, object]] | None = None
    tools: list[dict[str, object]] | None = None
    hooks: list[dict[str, object]] | None = None
    orchestrator: dict[str, object] | None = None
    context_manager: dict[str, object] | None = None
    agents: dict[str, str] | None = None
    context_refs: dict[str, str] | None = None
    instruction: str | None = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.providers is None:
            self.providers = []
        if self.tools is None:
            self.tools = []
        if self.hooks is None:
            self.hooks = []


class ProfileService:
    """Simple profile management service.

    Scans flat profiles directory for profiles:
    - profiles/{collection}/*.yaml (collection profiles)
    - profiles/*.yaml (standalone profiles)

    Handles one-level inheritance via 'extends' field and stores
    active profile in a text file.

    Can optionally integrate with ProfileDiscoveryService and ProfileCompilationService
    for schema v2 profile support.
    """

    def __init__(
        self,
        share_dir: Path,
        data_dir: Path,
        discovery_service: ProfileDiscoveryService | None = None,
        compilation_service: ProfileCompilationService | None = None,
    ) -> None:
        """Initialize profile service.

        Args:
            share_dir: Root share directory containing profiles/
            data_dir: Directory for service data (active profile file)
            discovery_service: Optional ProfileDiscoveryService (for schema v2)
            compilation_service: Optional ProfileCompilationService (for ref resolution)
        """
        self.share_dir = Path(share_dir)
        self.profiles_dir = self.share_dir / "profiles"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_profile_file = self.data_dir / "active_profile.txt"

        # New services (optional for backward compatibility)
        self.discovery_service = discovery_service
        self.compilation_service = compilation_service

        service_status = []
        if discovery_service:
            service_status.append("discovery")
        if compilation_service:
            service_status.append("compilation")

        services_str = f" (with {', '.join(service_status)})" if service_status else ""
        logger.info(
            f"ProfileService initialized with share_dir={self.share_dir}, data_dir={self.data_dir}{services_str}"
        )

    def list_profiles(self) -> list[ProfileInfo]:
        """List all available profiles.

        Combines profiles from:
        - Local .yaml files (legacy schema v1)
        - Cached profiles from ProfileDiscoveryService (schema v2)

        Returns:
            List of ProfileInfo objects
        """
        profiles = []
        active_name = self._read_active_profile()
        profile_names_seen = set()

        # First, get cached profiles from discovery service (schema v2)
        if self.discovery_service:
            logger.debug("Listing cached profiles from discovery service")
            try:
                cached_profiles = self.discovery_service.list_cached_profiles()
                for profile_detail in cached_profiles:
                    profile_names_seen.add(profile_detail.name)
                    profiles.append(
                        ProfileInfo(
                            name=profile_detail.name,
                            source=profile_detail.source,
                            is_active=(profile_detail.name == active_name),
                            collection_id=profile_detail.collection_id,
                            schema_version=profile_detail.schema_version,
                        )
                    )
                logger.debug(f"Added {len(cached_profiles)} cached profiles (schema v2)")
            except Exception as e:
                logger.error(f"Error listing cached profiles: {e}")

        # Then scan local .yaml and .md files (schema v1 / legacy and schema v2)
        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory does not exist: {self.profiles_dir}")
            return profiles

        # Scan both .yaml (schema v1) and .md (schema v2) files
        # Only look for profile files in the top 2 levels (collection/profile/*.md)
        # This skips module documentation nested in providers/tools/hooks subdirectories
        import itertools

        yaml_files = self.profiles_dir.rglob("*.yaml")
        # Only scan for .md files that are close to the profiles root (not deeply nested)
        # Profile structure: profiles/collection/profile-name/profile-name.md
        # Module docs are deeper: profiles/collection/profile-name/providers/hash/README.md
        md_files = (f for f in self.profiles_dir.rglob("*.md") if len(f.relative_to(self.profiles_dir).parts) <= 3)

        for profile_file in itertools.chain(yaml_files, md_files):
            if not profile_file.is_file():
                continue

            try:
                profile_data = self._load_profile_file(profile_file)

                # Skip if already added from discovery service
                if profile_data.name in profile_names_seen:
                    logger.debug(f"Skipping {profile_data.name} (already in cached profiles)")
                    continue

                profile_names_seen.add(profile_data.name)
                relative = profile_file.relative_to(self.profiles_dir)

                if len(relative.parts) > 1:
                    source = f"{relative.parts[0]}/profiles/{relative.name}"
                else:
                    source = f"profiles/{relative.name}"

                profiles.append(
                    ProfileInfo(
                        name=profile_data.name,
                        source=source,
                        is_active=(profile_data.name == active_name),
                    )
                )
            except Exception as e:
                # Skip files that aren't valid profiles (README, docs, etc.)
                # Only log at debug level since this is expected for non-profile markdown files
                logger.debug(f"Skipping {profile_file.name}: not a valid profile ({e})")

        logger.info(f"Found {len(profiles)} total profiles")
        return profiles

    def get_profile(self, name: str) -> ProfileDetails:
        """Get detailed information about a profile, resolving inheritance.

        Note: Schema v2 profiles do not support inheritance via 'extends'.
        Use ProfileCompilationService for ref resolution instead.

        Args:
            name: Profile name

        Returns:
            ProfileDetails object with resolved inheritance (schema v1 only)

        Raises:
            FileNotFoundError: If profile does not exist
        """
        profile_file = self._find_profile_file(name)
        profile_data = self._load_profile_file(profile_file)

        # Check schema version
        if profile_data.schema_version == 2:
            logger.debug(f"Profile {name} is schema v2, skipping inheritance resolution")
            if profile_data.extends:
                logger.warning(
                    f"Profile {name} has schema_version: 2 but uses 'extends' field. "
                    "Schema v2 profiles should use refs instead of inheritance. "
                    "The 'extends' field will be ignored."
                )
        else:
            # Schema v1: handle inheritance
            inheritance_chain = [profile_data.name]
            base_data = None

            if profile_data.extends:
                logger.debug(f"Resolving inheritance for schema v1 profile: {name}")
                try:
                    base_file = self._find_profile_file(profile_data.extends)
                    base_data = self._load_profile_file(base_file)
                    inheritance_chain.append(base_data.name)
                except FileNotFoundError:
                    logger.warning(f"Base profile not found: {profile_data.extends}")

            if base_data:
                profile_data = self._merge_profiles(base_data, profile_data)

        active_name = self._read_active_profile()
        source = self._get_profile_source(profile_file)
        collection_id = _get_collection_from_source(source)

        # Build SessionConfig if we have orchestrator or context_manager
        session = None
        if profile_data.orchestrator or profile_data.context_manager:
            # Convert orchestrator dict to ModuleConfig
            orchestrator_config = None
            if profile_data.orchestrator:
                module_val = profile_data.orchestrator.get("module", "")
                source_val = profile_data.orchestrator.get("source")
                config_val = profile_data.orchestrator.get("config")
                orchestrator_config = ModuleConfig(
                    module=str(module_val) if module_val else "",
                    source=str(source_val) if source_val and isinstance(source_val, str) else None,
                    config=config_val if isinstance(config_val, dict) else None,
                )

            # Convert context_manager dict to ModuleConfig
            context_manager_config = None
            if profile_data.context_manager:
                module_val = profile_data.context_manager.get("module", "")
                source_val = profile_data.context_manager.get("source")
                config_val = profile_data.context_manager.get("config")
                context_manager_config = ModuleConfig(
                    module=str(module_val) if module_val else "",
                    source=str(source_val) if source_val and isinstance(source_val, str) else None,
                    config=config_val if isinstance(config_val, dict) else None,
                )

            # Only create SessionConfig if we have at least orchestrator
            if orchestrator_config:
                session = SessionConfig(
                    orchestrator=orchestrator_config,
                    context_manager=context_manager_config,
                )

        return ProfileDetails(
            name=profile_data.name,
            schema_version=profile_data.schema_version,
            version=profile_data.version,
            description=profile_data.description,
            collection_id=collection_id,
            source=source,
            is_active=(profile_data.name == active_name),
            providers=self._convert_module_configs(profile_data.providers or []),
            tools=self._convert_module_configs(profile_data.tools or []),
            hooks=self._convert_module_configs(profile_data.hooks or []),
            session=session,
            agents=list(profile_data.agents.keys()) if profile_data.agents else [],
            context=profile_data.context_refs or {},
            instruction=profile_data.instruction,
        )

    def get_active_profile(self) -> ProfileDetails | None:
        """Get the currently active profile.

        Returns:
            ProfileDetails object or None if no profile is active
        """
        active_name = self._read_active_profile()
        if not active_name:
            return None

        try:
            return self.get_profile(active_name)
        except FileNotFoundError:
            logger.warning(f"Active profile not found: {active_name}")
            self._write_active_profile(None)
            return None

    def activate_profile(self, name: str) -> None:
        """Activate a profile.

        Args:
            name: Profile name

        Raises:
            FileNotFoundError: If profile does not exist
        """
        profile_file = self._find_profile_file(name)
        profile_data = self._load_profile_file(profile_file)

        self._write_active_profile(profile_data.name)
        logger.info(f"Activated profile: {profile_data.name}")

    def deactivate_profile(self) -> None:
        """Deactivate the currently active profile."""
        self._write_active_profile(None)
        logger.info("Deactivated profile")

    def _find_profile_file(self, name: str) -> Path:
        """Find profile file by name across all profiles.

        Searches for both .yaml (schema v1) and .md (schema v2) profile files.

        Args:
            name: Profile name

        Returns:
            Path to profile file

        Raises:
            FileNotFoundError: If profile not found
        """
        # Search for both .yaml and .md files
        for pattern in ["*.yaml", "*.md"]:
            for profile_file in self.profiles_dir.rglob(pattern):
                if not profile_file.is_file():
                    continue

                try:
                    profile_data = self._load_profile_file(profile_file)
                    if profile_data.name == name:
                        return profile_file
                except Exception:
                    continue

        raise FileNotFoundError(f"Profile not found: {name}")

    def _load_profile_file(self, profile_file: Path) -> ProfileData:
        """Load profile data from YAML or markdown file.

        Supports both:
        - .yaml files (schema v1): Pure YAML
        - .md files (schema v2): YAML frontmatter + markdown body

        Args:
            profile_file: Path to profile file (.yaml or .md)

        Returns:
            ProfileData object

        Raises:
            ValueError: If YAML is invalid or missing required fields
        """
        try:
            with open(profile_file) as f:
                content = f.read()

            # Extract markdown body if present
            markdown_body = None
            if profile_file.suffix == ".md" and content.startswith("---\n"):
                # Extract YAML frontmatter from markdown
                parts = content.split("---\n", 2)
                if len(parts) >= 3:
                    yaml_content = parts[1]
                    markdown_body = parts[2].strip() if len(parts) > 2 else None
                    data = yaml.safe_load(yaml_content)
                else:
                    raise ValueError(f"Invalid markdown frontmatter in {profile_file}")
            else:
                # Pure YAML file - no instruction
                markdown_body = None
                data = yaml.safe_load(content)

            if not data or not isinstance(data, dict):
                raise ValueError(f"Invalid profile YAML: {profile_file}")

            if "profile" not in data:
                raise ValueError(f"Missing 'profile' section in {profile_file}")

            profile = data["profile"]
            if "name" not in profile:
                raise ValueError(f"Missing 'name' in profile section: {profile_file}")

            # Extract schema_version from profile section
            schema_version = profile.get("schema_version", 1)

            # For schema v2, orchestrator and context_manager are in session section
            orchestrator = None
            context_manager = None
            if schema_version == 2 and "session" in data:
                session = data["session"]
                orchestrator = session.get("orchestrator")
                context_manager = session.get("context")  # This is the MODULE, not context refs
            else:
                # Schema v1 or legacy: orchestrator/context at root level
                orchestrator = data.get("orchestrator")
                context_manager = data.get("context")

            # Extract agents and context_refs from root level
            agents = data.get("agents")  # Dict of name -> file ref
            context_refs = data.get("context")  # Dict of name -> directory ref

            # Handle schema v2 case where root-level context exists
            if schema_version == 2 and "context" in data:
                # Root-level context is the context REFS, not the context manager
                context_refs = data.get("context")

            return ProfileData(
                name=profile["name"],
                version=profile.get("version", "0.0.0"),
                description=profile.get("description", ""),
                schema_version=schema_version,
                extends=profile.get("extends"),
                providers=data.get("providers", []),
                tools=data.get("tools", []),
                hooks=data.get("hooks", []),
                orchestrator=orchestrator,
                context_manager=context_manager,
                agents=agents,
                context_refs=context_refs,
                instruction=markdown_body,
            )
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file {profile_file}: {e}")

    def _merge_profiles(self, base: ProfileData, derived: ProfileData) -> ProfileData:
        """Merge derived profile with base profile (one-level inheritance).

        Args:
            base: Base profile data
            derived: Derived profile data

        Returns:
            Merged ProfileData object
        """
        base_providers = base.providers or []
        derived_providers = derived.providers or []
        base_tools = base.tools or []
        derived_tools = derived.tools or []
        base_hooks = base.hooks or []
        derived_hooks = derived.hooks or []

        return ProfileData(
            name=derived.name,
            version=derived.version,
            description=derived.description,
            extends=derived.extends,
            providers=base_providers + derived_providers,
            tools=base_tools + derived_tools,
            hooks=base_hooks + derived_hooks,
            orchestrator=derived.orchestrator or base.orchestrator,
            context_manager=derived.context_manager or base.context_manager,
            agents={**(base.agents or {}), **(derived.agents or {})},
            context_refs={**(base.context_refs or {}), **(derived.context_refs or {})},
            instruction=derived.instruction or base.instruction,
        )

    def _convert_module_configs(self, configs: list[dict[str, object]]) -> list[ModuleConfig]:
        """Convert raw config dictionaries to ModuleConfig objects.

        Args:
            configs: List of raw module configuration dictionaries

        Returns:
            List of ModuleConfig objects
        """
        result = []
        for config in configs:
            module = config.get("module", "")
            source = config.get("source")
            module_config = config.get("config")

            if not isinstance(module, str):
                module = ""
            if source is not None and not isinstance(source, str):
                source = None
            if module_config is not None and not isinstance(module_config, dict):
                module_config = None

            result.append(
                ModuleConfig(
                    module=module,
                    source=source,
                    config=module_config,
                )
            )
        return result

    def _get_profile_source(self, profile_file: Path) -> str:
        """Get profile source string (collection/profiles/filename or profiles/filename).

        Args:
            profile_file: Path to profile file

        Returns:
            Source string
        """
        try:
            relative = profile_file.relative_to(self.profiles_dir)
            if len(relative.parts) > 1:
                return f"{relative.parts[0]}/profiles/{relative.name}"
            return f"profiles/{relative.name}"
        except ValueError:
            return str(profile_file)

    def _read_active_profile(self) -> str | None:
        """Read active profile name from file.

        Returns:
            Active profile name or None
        """
        if not self.active_profile_file.exists():
            return None

        try:
            content = self.active_profile_file.read_text().strip()
            return content if content else None
        except Exception as e:
            logger.error(f"Error reading active profile file: {e}")
            return None

    def _write_active_profile(self, name: str | None) -> None:
        """Write active profile name to file.

        Args:
            name: Profile name or None to clear
        """
        try:
            if name:
                self.active_profile_file.write_text(name + "\n")
            else:
                if self.active_profile_file.exists():
                    self.active_profile_file.unlink()
        except Exception as e:
            logger.error(f"Error writing active profile file: {e}")
            raise

    def compile_and_activate_profile(self, collection_id: str, profile_name: str) -> Path:
        """Compile profile and activate it (schema v2 profiles only).

        Uses ProfileCompilationService to resolve all refs and create a
        compiled profile directory, then activates the profile.

        Args:
            collection_id: Collection ID
            profile_name: Profile name

        Returns:
            Path to compiled profile directory

        Raises:
            ValueError: If compilation_service not available
            FileNotFoundError: If profile not found
        """
        if not self.compilation_service:
            raise ValueError(
                "Profile compilation not available. compilation_service must be provided during initialization."
            )

        logger.info(f"Compiling profile: {collection_id}/{profile_name}")

        # Get profile from discovery service or scan
        profile = None
        if self.discovery_service:
            profile = self.discovery_service.get_cached_profile(collection_id, profile_name)
            if profile:
                logger.debug(f"Found profile in discovery cache: {profile_name}")

        if not profile:
            logger.debug(f"Profile not in cache, attempting to load from file: {profile_name}")
            try:
                profile = self.get_profile(profile_name)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Profile not found: {collection_id}/{profile_name}. "
                    "Profile must be discovered first or exist as local .yaml file."
                )

        # Compile profile
        logger.info(f"Compiling profile with compilation service: {profile.name}")
        compiled_path = self.compilation_service.compile_profile(collection_id, profile)

        # Activate
        logger.info(f"Activating compiled profile: {profile.name}")
        self._write_active_profile(profile.name)

        logger.info(f"Profile compiled and activated: {profile.name} → {compiled_path}")
        return compiled_path

    def create_profile(self, request: CreateProfileRequest) -> ProfileDetails:
        """Create new profile in local collection.

        Args:
            request: Profile creation request

        Returns:
            Created profile details

        Raises:
            ValueError: If profile name already exists
        """
        from amplifierd.models.profiles import CreateProfileRequest

        if not isinstance(request, CreateProfileRequest):
            request = CreateProfileRequest(**request)

        existing_profiles = self.list_profiles()
        if any(p.name == request.name for p in existing_profiles):
            raise ValueError(f"Profile '{request.name}' already exists")

        local_profile_dir = self.profiles_dir / "local" / request.name
        local_profile_dir.mkdir(parents=True, exist_ok=True)

        profile_details = ProfileDetails(
            name=request.name,
            schema_version=2,
            version=request.version,
            description=request.description,
            collection_id="local",
            source=f"local/profiles/{request.name}.md",
            is_active=False,
            providers=request.providers,
            tools=request.tools,
            hooks=request.hooks,
        )

        manifest_content = self._generate_profile_manifest(
            profile_details,
            request.orchestrator,
            request.context,
            None,  # agents (not supported in CreateProfileRequest yet)
            None,  # contexts (not supported in CreateProfileRequest yet)
            None,  # instruction (not supported in CreateProfileRequest yet)
        )
        manifest_file = local_profile_dir / "profile.md"
        manifest_file.write_text(manifest_content)

        logger.info(f"Created local profile: {request.name}")
        return profile_details

    def copy_profile(self, source_name: str, new_name: str) -> ProfileDetails:
        """Copy profile from any collection to local collection with new name.

        Creates a copy of an existing profile in the local collection with all
        fields preserved except the name. The source profile can be from any
        collection (local, discovered, etc).

        Args:
            source_name: Name of profile to copy from
            new_name: Name for the copied profile (kebab-case)

        Returns:
            ProfileDetails of the newly created profile

        Raises:
            FileNotFoundError: If source profile doesn't exist
            ValueError: If new_name format invalid or already exists
        """
        import re

        # 1. Validate new_name format (kebab-case pattern)
        if not re.match(r"^[a-z0-9-]+$", new_name):
            raise ValueError(
                f"Invalid profile name '{new_name}'. Name must contain only lowercase letters, numbers, and hyphens."
            )

        # 2. Check if new_name already exists in local collection
        existing_profiles = self.list_profiles()
        local_profiles = [p for p in existing_profiles if p.source.startswith("local/")]
        if any(p.name == new_name for p in local_profiles):
            raise ValueError(f"Profile '{new_name}' already exists in local collection")

        # 3. Get source profile (from any collection)
        source_profile = self.get_profile(source_name)

        # 4. Create copy request with all fields from source
        orchestrator = None
        context = None
        if source_profile.session:
            orchestrator = source_profile.session.orchestrator
            context = source_profile.session.context_manager

        copy_request = CreateProfileRequest(
            name=new_name,
            version=source_profile.version,
            description=source_profile.description,
            providers=source_profile.providers,
            tools=source_profile.tools,
            hooks=source_profile.hooks,
            orchestrator=orchestrator,
            context=context,
        )

        # 5. Create the new profile using existing create_profile method
        new_profile = self.create_profile(copy_request)

        # 6. If source has instruction, agents, or contexts, update the profile
        if source_profile.instruction or source_profile.agents or source_profile.context:
            local_profile_dir = self.profiles_dir / "local" / new_name

            # Build agents dict from list
            agents = {agent: agent for agent in source_profile.agents} if source_profile.agents else None

            manifest_content = self._generate_profile_manifest(
                new_profile,
                orchestrator,
                context,
                agents,
                source_profile.context,  # context refs
                source_profile.instruction,
            )

            manifest_file = local_profile_dir / "profile.md"
            manifest_file.write_text(manifest_content)
            logger.info(f"Updated copied profile with instruction/agents/contexts: {new_name}")

        # 7. Re-read the profile to get complete ProfileDetails with instruction
        return self.get_profile(new_name)

    def update_profile(self, name: str, request: UpdateProfileRequest) -> ProfileDetails:
        """Update existing local profile.

        Args:
            name: Profile name
            request: Update request with partial fields

        Returns:
            Updated profile details

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If profile not in local collection
        """
        from amplifierd.models.profiles import UpdateProfileRequest

        if not isinstance(request, UpdateProfileRequest):
            request = UpdateProfileRequest(**request)

        current = self.get_profile(name)

        self._validate_local_ownership(current)

        updated = ProfileDetails(
            name=current.name,
            schema_version=current.schema_version,
            version=request.version if request.version is not None else current.version,
            description=request.description if request.description is not None else current.description,
            collection_id=current.collection_id,
            source=current.source,
            is_active=current.is_active,
            providers=request.providers if request.providers is not None else current.providers,
            tools=request.tools if request.tools is not None else current.tools,
            hooks=request.hooks if request.hooks is not None else current.hooks,
            agents=list(request.agents.keys()) if request.agents is not None else current.agents,
            context=request.contexts if request.contexts is not None else current.context,
            instruction=request.instruction if request.instruction is not None else current.instruction,
        )

        orchestrator = request.orchestrator if request.orchestrator is not None else None
        context = request.context if request.context is not None else None

        agents = (
            request.agents
            if request.agents is not None
            else ({agent: agent for agent in current.agents} if current.agents else None)
        )
        contexts = request.contexts if request.contexts is not None else current.context
        instruction = request.instruction if request.instruction is not None else current.instruction

        local_profile_dir = self.profiles_dir / "local" / name
        manifest_content = self._generate_profile_manifest(
            updated, orchestrator, context, agents, contexts, instruction
        )
        manifest_file = local_profile_dir / "profile.md"
        manifest_file.write_text(manifest_content)

        logger.info(f"Updated local profile: {name}")
        return updated

    def delete_profile(self, name: str) -> None:
        """Delete local profile.

        Args:
            name: Profile name

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If profile not local or is active
        """
        profile = self.get_profile(name)

        self._validate_local_ownership(profile)

        if profile.is_active:
            raise ValueError(f"Cannot delete active profile '{name}'. Deactivate it first.")

        local_profile_dir = self.profiles_dir / "local" / name
        if local_profile_dir.exists():
            shutil.rmtree(local_profile_dir)
            logger.info(f"Deleted local profile: {name}")
        else:
            raise FileNotFoundError(f"Profile directory not found: {name}")

    def _validate_local_ownership(self, profile: ProfileDetails) -> None:
        """Ensure profile is in local collection.

        Args:
            profile: Profile to validate

        Raises:
            ValueError: If profile not in local collection
        """
        collection_id = profile.collection_id or self._extract_collection_from_source(profile.source)

        if collection_id != "local":
            raise ValueError(
                f"Cannot modify profile '{profile.name}' from collection '{collection_id}'. "
                "Only profiles in 'local' collection can be modified."
            )

    def _extract_collection_from_source(self, source: str) -> str | None:
        """Extract collection ID from source path."""
        parts = source.split("/")
        if len(parts) > 0 and parts[0]:
            return parts[0]
        return None

    def _generate_profile_manifest(
        self,
        profile: ProfileDetails,
        orchestrator: ModuleConfig | None = None,
        context: ModuleConfig | None = None,
        agents: dict[str, str] | None = None,
        contexts: dict[str, str] | None = None,
        instruction: str | None = None,
    ) -> str:
        """Generate .md file content with YAML frontmatter.

        Args:
            profile: Profile details
            orchestrator: Orchestrator module config
            context: Context module config
            agents: Agent file references (name -> ref)
            contexts: Context directory references (name -> ref)
            instruction: Profile system instruction

        Returns:
            Markdown content with YAML frontmatter
        """
        session_data: dict[str, object] = {}

        if orchestrator:
            session_data["orchestrator"] = {
                "module": orchestrator.module,
                "source": orchestrator.source,
                "config": orchestrator.config or {},
            }

        if context:
            session_data["context"] = {
                "module": context.module,
                "source": context.source,
                "config": context.config or {},
            }

        yaml_data: dict[str, object] = {
            "profile": {
                "name": profile.name,
                "schema_version": profile.schema_version,
                "version": profile.version,
                "description": profile.description,
            },
            "session": session_data,
        }

        if profile.providers:
            yaml_data["providers"] = [
                {"module": p.module, "source": p.source, **({"config": p.config} if p.config else {})}
                for p in profile.providers
            ]

        if profile.tools:
            yaml_data["tools"] = [
                {"module": t.module, "source": t.source, **({"config": t.config} if t.config else {})}
                for t in profile.tools
            ]

        if profile.hooks:
            yaml_data["hooks"] = [
                {"module": h.module, "source": h.source, **({"config": h.config} if h.config else {})}
                for h in profile.hooks
            ]

        if agents:
            yaml_data["agents"] = agents

        if contexts:
            yaml_data["context"] = contexts

        yaml_content = yaml.dump(yaml_data, sort_keys=False, allow_unicode=True, default_flow_style=False)

        if instruction:
            markdown_body = instruction
        else:
            # Default markdown body if no custom instruction
            markdown_body = f"# {profile.name}\n\n{profile.description}\n"

        return f"---\n{yaml_content}---\n\n{markdown_body}"
