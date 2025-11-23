"""Simple profile management service.

Scans flat profiles directory for profiles, handles one-level inheritance,
and manages active profile state in a simple text file.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.models.profiles import ProfileInfo

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
    extends: str | None = None
    providers: list[dict[str, object]] | None = None
    tools: list[dict[str, object]] | None = None
    hooks: list[dict[str, object]] | None = None
    orchestrator: dict[str, object] | None = None
    context: dict[str, object] | None = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.providers is None:
            self.providers = []
        if self.tools is None:
            self.tools = []
        if self.hooks is None:
            self.hooks = []


class SimpleProfileService:
    """Simple profile management service.

    Scans flat profiles directory for profiles:
    - profiles/{collection}/*.yaml (collection profiles)
    - profiles/*.yaml (standalone profiles)

    Handles one-level inheritance via 'extends' field and stores
    active profile in a text file.
    """

    def __init__(self, share_dir: Path, data_dir: Path) -> None:
        """Initialize profile service.

        Args:
            share_dir: Root share directory containing profiles/
            data_dir: Directory for service data (active profile file)
        """
        self.share_dir = Path(share_dir)
        self.profiles_dir = self.share_dir / "profiles"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_profile_file = self.data_dir / "active_profile.txt"
        logger.info(f"SimpleProfileService initialized with share_dir={self.share_dir}, data_dir={self.data_dir}")

    def list_profiles(self) -> list[ProfileInfo]:
        """List all available profiles.

        Returns:
            List of ProfileInfo objects
        """
        profiles = []
        active_name = self._read_active_profile()

        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory does not exist: {self.profiles_dir}")
            return profiles

        for profile_file in self.profiles_dir.rglob("*.yaml"):
            if not profile_file.is_file():
                continue

            try:
                profile_data = self._load_profile_file(profile_file)
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
                logger.error(f"Error loading profile {profile_file}: {e}")

        logger.info(f"Found {len(profiles)} profiles")
        return profiles

    def get_profile(self, name: str) -> ProfileDetails:
        """Get detailed information about a profile, resolving inheritance.

        Args:
            name: Profile name

        Returns:
            ProfileDetails object with resolved inheritance

        Raises:
            FileNotFoundError: If profile does not exist
        """
        profile_file = self._find_profile_file(name)
        profile_data = self._load_profile_file(profile_file)

        inheritance_chain = [profile_data.name]
        base_data = None

        if profile_data.extends:
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

        return ProfileDetails(
            name=profile_data.name,
            version=profile_data.version,
            description=profile_data.description,
            source=source,
            is_active=(profile_data.name == active_name),
            inheritance_chain=inheritance_chain,
            providers=self._convert_module_configs(profile_data.providers or []),
            tools=self._convert_module_configs(profile_data.tools or []),
            hooks=self._convert_module_configs(profile_data.hooks or []),
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

        Args:
            name: Profile name

        Returns:
            Path to profile file

        Raises:
            FileNotFoundError: If profile not found
        """
        for profile_file in self.profiles_dir.rglob("*.yaml"):
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
        """Load profile data from YAML file.

        Args:
            profile_file: Path to profile YAML file

        Returns:
            ProfileData object

        Raises:
            ValueError: If YAML is invalid or missing required fields
        """
        try:
            with open(profile_file) as f:
                data = yaml.safe_load(f)

            if not data or not isinstance(data, dict):
                raise ValueError(f"Invalid profile YAML: {profile_file}")

            if "profile" not in data:
                raise ValueError(f"Missing 'profile' section in {profile_file}")

            profile = data["profile"]
            if "name" not in profile:
                raise ValueError(f"Missing 'name' in profile section: {profile_file}")

            return ProfileData(
                name=profile["name"],
                version=profile.get("version", "0.0.0"),
                description=profile.get("description", ""),
                extends=profile.get("extends"),
                providers=data.get("providers", []),
                tools=data.get("tools", []),
                hooks=data.get("hooks", []),
                orchestrator=data.get("orchestrator"),
                context=data.get("context"),
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
            context={**(base.context or {}), **(derived.context or {})},
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

    def sync_profile_modules(self, profile_name: str) -> dict[str, str]:
        """Sync modules for a profile.

        Resolves and caches all module dependencies from the profile's sources.

        Args:
            profile_name: Profile name

        Returns:
            Dictionary mapping module_id to status ("resolved", "cached", "error")

        Raises:
            FileNotFoundError: If profile not found
        """
        from .module_resolver_service import get_module_resolver_service

        profile_file = self._find_profile_file(profile_name)
        source = self._get_profile_source(profile_file)
        collection_name = _get_collection_from_source(source)

        if not collection_name:
            logger.warning(f"Profile {profile_name} not from a collection, no modules to sync")
            return {}

        resolver = get_module_resolver_service()
        results = resolver.resolve_module_dependencies(profile_file, collection_name)

        logger.info(f"Synced {len(results)} modules for profile {profile_name}")
        return results
