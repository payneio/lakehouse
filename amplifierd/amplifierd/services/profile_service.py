"""V3 profile management service.

Manages v3 profiles with flat directory structure (no collections).
Scans share/profiles/ for compiled profiles and handles compilation via ProfileCompilationService.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from amplifierd.services.profile_compilation import ProfileCompilationService

from amplifier_library.services.registry_service import RegistryService
from amplifierd.models.profiles import BehaviorRef
from amplifierd.models.profiles import CreateProfileRequest
from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.models.profiles import ProfileInfo
from amplifierd.models.profiles import SessionConfig
from amplifierd.models.profiles import UpdateProfileRequest

logger = logging.getLogger(__name__)


class ProfileService:
    """V3 profile management service.

    Manages profiles in flat share/profiles/ directory structure.
    Each profile is a directory containing mount_plan.json.
    """

    def __init__(
        self,
        share_dir: Path,
        cache_dir: Path,
        data_dir: Path,
        registry_service: RegistryService,
        compilation_service: ProfileCompilationService | None = None,
    ) -> None:
        """Initialize profile service.

        Args:
            share_dir: Root share directory containing profiles/
            cache_dir: Cache directory for compilation
            data_dir: Directory for service data (active profile file)
            registry_service: Registry service for amp:// resolution
            compilation_service: Optional ProfileCompilationService
        """
        self.share_dir = Path(share_dir)
        self.cache_dir = Path(cache_dir)
        self.profiles_dir = self.share_dir / "profiles"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_profile_file = self.data_dir / "active_profile.txt"
        self.registry_service = registry_service
        self.compilation_service = compilation_service

        logger.info(
            f"ProfileService initialized: share_dir={self.share_dir}, "
            f"cache_dir={self.cache_dir}, data_dir={self.data_dir}"
        )

    def list_profiles(self) -> list[ProfileInfo]:
        """List all profiles.

        Scans share/profiles/ for directories containing profile.yaml.

        Returns:
            List of ProfileInfo objects
        """
        profiles = []
        active_profile = self.get_active_profile()

        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory does not exist: {self.profiles_dir}")
            return profiles

        # Scan flat profile directories
        for profile_dir in self.profiles_dir.iterdir():
            if not profile_dir.is_dir():
                continue

            # Check for profile.yaml (new format)
            profile_yaml_path = profile_dir / "profile.yaml"
            if not profile_yaml_path.exists():
                logger.debug(f"Skipping {profile_dir.name}: no profile.yaml")
                continue

            # Load minimal info from profile.yaml
            import yaml

            try:
                profile_data = yaml.safe_load(profile_yaml_path.read_text())
                profile_info = profile_data.get("profile", {})
                profile_name = profile_info.get("name", profile_dir.name)

                profiles.append(
                    ProfileInfo(
                        name=profile_name,
                        source=str(profile_dir),
                        source_type="local",
                        registry_id=None,
                        source_uri=None,
                        is_active=(profile_name == active_profile),
                        schema_version=3,
                    )
                )
                logger.debug(f"Found profile: {profile_name}")
            except Exception as e:
                logger.warning(f"Failed to parse {profile_yaml_path}: {e}")

        logger.info(f"Found {len(profiles)} profiles")
        return profiles

    def compile_profile(self, profile_id: str, profile_yaml: dict, config_yaml: dict) -> Path:
        """Compile v3 profile.

        Args:
            profile_id: Profile identifier
            profile_yaml: Parsed profile YAML dictionary
            config_yaml: Parsed config YAML dictionary

        Returns:
            Path to compiled profile directory

        Raises:
            ValueError: If ProfileCompilationService not available
        """
        if not self.compilation_service:
            raise ValueError("ProfileCompilationService not available")

        logger.info(f"Compiling profile: {profile_id}")
        return self.compilation_service.compile_profile(
            profile_id=profile_id, profile_yaml=profile_yaml, config_yaml=config_yaml
        )

    def get_active_profile(self) -> str | None:
        """Get the currently active profile name.

        Returns:
            Profile name or None if no profile is active
        """
        if not self.active_profile_file.exists():
            return None

        try:
            content = self.active_profile_file.read_text().strip()
            return content if content else None
        except Exception as e:
            logger.error(f"Error reading active profile file: {e}")
            return None

    def set_active_profile(self, profile_name: str | None) -> None:
        """Set the active profile.

        Args:
            profile_name: Profile name or None to clear
        """
        try:
            if profile_name:
                self.active_profile_file.write_text(profile_name + "\n")
                logger.info(f"Set active profile: {profile_name}")
            else:
                if self.active_profile_file.exists():
                    self.active_profile_file.unlink()
                logger.info("Cleared active profile")
        except Exception as e:
            logger.error(f"Error writing active profile file: {e}")
            raise

    def activate_profile(self, profile_name: str) -> None:
        """Activate a profile by name.

        Args:
            profile_name: Profile name to activate

        Raises:
            FileNotFoundError: If profile does not exist
        """
        # Verify profile exists
        profile_dir = self.profiles_dir / profile_name
        if not profile_dir.exists() or not (profile_dir / "profile.yaml").exists():
            raise FileNotFoundError(f"Profile not found: {profile_name}")

        self.set_active_profile(profile_name)
        logger.info(f"Activated profile: {profile_name}")

    def deactivate_profile(self) -> None:
        """Deactivate the currently active profile."""
        self.set_active_profile(None)
        logger.info("Deactivated profile")

    def create_profile(self, request: CreateProfileRequest) -> ProfileDetails:
        """Create a new profile.

        Args:
            request: Profile creation request

        Returns:
            Created profile details

        Raises:
            ValueError: If profile already exists or validation fails
        """
        import yaml

        if not self.compilation_service:
            raise ValueError("ProfileCompilationService not available")

        profile_dir = self.profiles_dir / request.name

        # Verify profile doesn't exist
        if profile_dir.exists():
            raise ValueError(f"Profile already exists: {request.name}")

        logger.info(f"Creating profile: {request.name}")

        # Create profile directory
        profile_dir.mkdir(parents=True)

        # Build profile YAML structure (source)
        profile_yaml: dict[str, object] = {
            "profile": {
                "name": request.name,
                "version": request.version,
                "description": request.description,
                "schema_version": 3,
            },
            "behaviors": [],
        }

        # Add orchestrator and context if provided
        if request.orchestrator:
            orch_config: dict[str, object] = {
                "id": request.orchestrator.module,
                "source": request.orchestrator.source,
            }
            if request.orchestrator.config:
                orch_config["config"] = request.orchestrator.config
            profile_yaml["orchestrator"] = orch_config

        if request.context:
            ctx_config: dict[str, object] = {"id": request.context.module, "source": request.context.source}
            if request.context.config:
                ctx_config["config"] = request.context.config
            profile_yaml["context"] = ctx_config

        # Add providers with configs
        if request.providers:
            profile_yaml["providers"] = [
                {"id": p.module, "source": p.source, "config": p.config or {}} for p in request.providers
            ]

        # Add tools with configs
        if request.tools:
            profile_yaml["tools"] = [
                {"id": t.module, "source": t.source, "config": t.config or {}} for t in request.tools
            ]

        # Add hooks with configs
        if request.hooks:
            profile_yaml["hooks"] = [
                {"id": h.module, "source": h.source, "config": h.config or {}} for h in request.hooks
            ]

        # Add empty agents and contexts (user can add later)
        profile_yaml["agents"] = {}
        profile_yaml["contexts"] = []

        # Write profile.yaml (source)
        (profile_dir / "profile.yaml").write_text(yaml.dump(profile_yaml, default_flow_style=False))

        # Create metadata
        metadata = {
            "name": request.name,
            "source_type": "local",
            "registry_ref": None,
            "editable": True,
            "last_compiled": None,
        }
        (profile_dir / ".metadata.json").write_text(json.dumps(metadata, indent=2))

        # Build config YAML structure for compilation
        config_yaml: dict[str, object] = {"session": {}}

        # Add configurations for each component
        if request.orchestrator and request.orchestrator.config:
            if "session" not in config_yaml:
                config_yaml["session"] = {}
            config_yaml["session"]["orchestrator"] = request.orchestrator.config  # type: ignore

        if request.context and request.context.config:
            if "session" not in config_yaml:
                config_yaml["session"] = {}
            config_yaml["session"]["context"] = request.context.config  # type: ignore

        if request.providers:
            config_yaml["providers"] = {p.module: p.config or {} for p in request.providers}

        # Compile the profile (creates mount_plan.json)
        self.compilation_service.compile_profile(
            profile_id=request.name, profile_yaml=profile_yaml, config_yaml=config_yaml
        )

        # Mark as local
        (profile_dir / ".local").touch()

        logger.info(f"Profile created successfully: {request.name}")

        # Return the profile details
        return self.get_profile(request.name)

    def copy_profile(self, source_name: str, new_name: str) -> ProfileDetails:
        """Copy an existing profile with a new name.

        Args:
            source_name: Name of profile to copy
            new_name: Name for the new profile

        Returns:
            Created profile details

        Raises:
            FileNotFoundError: If source profile not found
            ValueError: If new name already exists
        """
        import shutil

        from amplifierd.startup import save_profile_source

        source_dir = self.profiles_dir / source_name
        new_dir = self.profiles_dir / new_name

        # Verify source exists
        if not source_dir.exists():
            raise FileNotFoundError(f"Source profile not found: {source_name}")

        # Verify new name doesn't exist
        if new_dir.exists():
            raise ValueError(f"Profile already exists: {new_name}")

        logger.info(f"Copying profile {source_name} to {new_name}")

        # Create new profile directory
        new_dir.mkdir(parents=True)

        # STEP 1: Copy or fetch profile.yaml
        source_yaml = source_dir / "profile.yaml"
        if source_yaml.exists():
            # Simple case: copy local profile's source
            shutil.copy2(source_yaml, new_dir / "profile.yaml")
            self._update_profile_name_in_yaml(new_dir / "profile.yaml", new_name)
            logger.info(f"Copied profile.yaml from {source_name} to {new_name}")
        else:
            # Complex case: fetch original source from registry
            logger.info(f"No local profile.yaml for {source_name}, fetching from registry")
            registry_source_dir = self._get_registry_source_dir(source_name)

            if registry_source_dir:
                # Found registry source - fetch it with assets
                logger.info(f"Found registry source for {source_name}: {registry_source_dir}")
                profile_yaml_text = self._get_registry_source_for_profile(source_name)

                if profile_yaml_text:
                    import yaml

                    profile_yaml = yaml.safe_load(profile_yaml_text)
                    profile_yaml["profile"]["name"] = new_name

                    # Use startup's helper to save source + assets
                    save_profile_source(new_name, profile_yaml, {}, registry_source_dir, self.profiles_dir)
                    logger.info(f"Fetched profile source and assets from registry for {new_name}")

                else:
                    # Couldn't load YAML - fall back
                    logger.warning(f"Failed to load registry source for {source_name}, using mount_plan")
                    self._create_yaml_from_mount_plan(source_dir, new_dir, new_name)
            else:
                # Last resort: create from mount_plan (loses agents/contexts)
                logger.warning(
                    f"No registry source found for {source_name}, using mount_plan (may lose agents/contexts)"
                )
                self._create_yaml_from_mount_plan(source_dir, new_dir, new_name)

        # STEP 2: Compile assets (for ALL copies, not just registry)
        if self.compilation_service:
            try:
                logger.info(f"Compiling assets for '{new_name}'...")

                # Read the profile.yaml we just created
                import yaml

                profile_yaml_path = new_dir / "profile.yaml"
                profile_yaml = yaml.safe_load(profile_yaml_path.read_text())

                # Compile to fetch and resolve all assets
                compiled_path = self.compilation_service.compile_profile(
                    profile_id=new_name, profile_yaml=profile_yaml, config_yaml={}
                )

                # Remove mount_plan.json (created per-session)
                mount_plan_path = compiled_path / "mount_plan.json"
                if mount_plan_path.exists():
                    mount_plan_path.unlink()
                    logger.debug("Removed mount_plan.json (created per-session)")

                logger.info(f"✓ Profile '{new_name}' assets compiled")
            except Exception as e:
                logger.warning(f"Failed to compile assets for '{new_name}': {e}")
        else:
            logger.debug("No compilation service available, skipping asset compilation")

        # Create metadata
        metadata = {
            "name": new_name,
            "source_type": "local",
            "registry_ref": None,
            "editable": True,
            "created_from": source_name,
        }
        (new_dir / ".metadata.json").write_text(json.dumps(metadata, indent=2))

        # Mark as local by creating a .local marker file
        (new_dir / ".local").touch()

        logger.info(f"Profile copied successfully: {new_name}")

        # Return the new profile details
        return self.get_profile(new_name)

    def _get_registry_source_for_profile(self, profile_name: str) -> str | None:
        """Get original source YAML from registry for a profile.

        Reads profiles.yaml to find the amp:// source, then fetches from cache.

        Args:
            profile_name: Profile name to fetch source for

        Returns:
            Original YAML source text or None if not found
        """
        import yaml

        # Read profiles.yaml
        profiles_config_path = self.share_dir / "profiles.yaml"
        if not profiles_config_path.exists():
            logger.debug(f"No profiles.yaml found at {profiles_config_path}")
            return None

        try:
            profiles_config = yaml.safe_load(profiles_config_path.read_text())
            profiles_list = profiles_config.get("profiles", [])

            # Find the profile entry
            for profile_entry in profiles_list:
                if isinstance(profile_entry, dict) and profile_name in profile_entry:
                    # Format: {profile_name: amp://uri}
                    amp_uri = profile_entry[profile_name]
                    logger.debug(f"Found amp:// URI for {profile_name}: {amp_uri}")

                    # Resolve amp:// URI to actual path
                    resolved_uri = self.registry_service.resolve_amp_uri(amp_uri)
                    logger.debug(f"Resolved to: {resolved_uri}")

                    # Use ref_resolution service to fetch (it handles caching)
                    if self.compilation_service:
                        ref_service = self.compilation_service.ref_resolution
                        resolved_path = ref_service.resolve_ref(resolved_uri)

                        if resolved_path.exists():
                            logger.info(f"Found registry source at: {resolved_path}")
                            return resolved_path.read_text()
                        logger.warning(f"Resolved path does not exist: {resolved_path}")

                    return None

            logger.debug(f"No entry found for {profile_name} in profiles.yaml")
            return None

        except Exception as e:
            logger.error(f"Failed to get registry source for {profile_name}: {e}")
            return None

    def _get_registry_source_dir(self, profile_name: str) -> Path | None:
        """Get registry source directory path for a profile.

        Reads profiles.yaml to find the amp:// source, resolves it to get the directory.

        Args:
            profile_name: Profile name to fetch source directory for

        Returns:
            Path to registry source directory or None if not found
        """
        import yaml

        # Read profiles.yaml
        profiles_config_path = self.share_dir / "profiles.yaml"
        if not profiles_config_path.exists():
            logger.debug(f"No profiles.yaml found at {profiles_config_path}")
            return None

        try:
            profiles_config = yaml.safe_load(profiles_config_path.read_text())
            profiles_list = profiles_config.get("profiles", [])

            # Find the profile entry
            for profile_entry in profiles_list:
                if isinstance(profile_entry, dict) and profile_name in profile_entry:
                    # Format: {profile_name: amp://uri}
                    amp_uri = profile_entry[profile_name]
                    logger.debug(f"Found amp:// URI for {profile_name}: {amp_uri}")

                    # Resolve amp:// URI to actual path
                    resolved_uri = self.registry_service.resolve_amp_uri(amp_uri)
                    logger.debug(f"Resolved to: {resolved_uri}")

                    # Use ref_resolution service to fetch (it handles caching)
                    if self.compilation_service:
                        ref_service = self.compilation_service.ref_resolution
                        resolved_path = ref_service.resolve_ref(resolved_uri)

                        if resolved_path.exists():
                            # Return parent directory if it's a file, otherwise the directory itself
                            if resolved_path.is_file():
                                logger.info(f"Found registry source file at: {resolved_path}")
                                return resolved_path.parent
                            logger.info(f"Found registry source directory at: {resolved_path}")
                            return resolved_path
                        logger.warning(f"Resolved path does not exist: {resolved_path}")

                    return None

            logger.debug(f"No entry found for {profile_name} in profiles.yaml")
            return None

        except Exception as e:
            logger.error(f"Failed to get registry source directory for {profile_name}: {e}")
            return None

    def _update_profile_name_in_yaml(self, yaml_path: Path, new_name: str) -> None:
        """Update profile name in YAML file.

        Args:
            yaml_path: Path to profile.yaml
            new_name: New profile name
        """
        import yaml

        yaml_data = yaml.safe_load(yaml_path.read_text())
        if "profile" not in yaml_data:
            yaml_data["profile"] = {}
        yaml_data["profile"]["name"] = new_name
        yaml_path.write_text(yaml.dump(yaml_data, default_flow_style=False))

    def _update_profile_name_in_mount_plan(self, mount_plan_path: Path, new_name: str) -> None:
        """Update profile name in mount_plan.json.

        Args:
            mount_plan_path: Path to mount_plan.json
            new_name: New profile name
        """
        mount_plan = json.loads(mount_plan_path.read_text())
        if "session" not in mount_plan:
            mount_plan["session"] = {}
        if "settings" not in mount_plan["session"]:
            mount_plan["session"]["settings"] = {}
        mount_plan["session"]["settings"]["profile_name"] = new_name
        mount_plan_path.write_text(json.dumps(mount_plan, indent=2))

    def _create_yaml_from_mount_plan(self, source_dir: Path, new_dir: Path, new_name: str) -> None:
        """Create profile.yaml from mount_plan.json for legacy profiles.

        Args:
            source_dir: Source profile directory
            new_dir: New profile directory
            new_name: New profile name
        """
        import yaml

        mount_plan_path = source_dir / "mount_plan.json"
        if not mount_plan_path.exists():
            raise ValueError(f"No mount_plan.json found in {source_dir}")

        mount_plan = json.loads(mount_plan_path.read_text())

        # Build profile YAML from mount_plan
        profile_yaml: dict[str, object] = {
            "profile": {"name": new_name, "version": "1.0.0", "description": "Copied from mount_plan"}
        }

        # Extract orchestrator
        session_data = mount_plan.get("session", {})
        if "orchestrator" in session_data:
            orch = session_data["orchestrator"]
            profile_yaml["orchestrator"] = {
                "id": orch.get("module", ""),
                "source": orch.get("source", ""),
                "config": orch.get("config", {}),
            }

        # Extract context
        if "context" in session_data:
            ctx = session_data["context"]
            profile_yaml["context"] = {
                "id": ctx.get("module", ""),
                "source": ctx.get("source", ""),
                "config": ctx.get("config", {}),
            }

        # Extract providers
        providers = mount_plan.get("providers", [])
        if providers:
            profile_yaml["providers"] = [
                {"id": p.get("module", ""), "source": p.get("source", ""), "config": p.get("config", {})}
                for p in providers
            ]

        # Extract tools
        tools = mount_plan.get("tools", [])
        if tools:
            profile_yaml["tools"] = [
                {"id": t.get("module", ""), "source": t.get("source", ""), "config": t.get("config", {})} for t in tools
            ]

        # Extract hooks
        hooks = mount_plan.get("hooks", [])
        if hooks:
            profile_yaml["hooks"] = [
                {"id": h.get("module", ""), "source": h.get("source", ""), "config": h.get("config", {})} for h in hooks
            ]

        # Note: agents and contexts from mount_plan are expanded content
        # We cannot reverse-engineer the refs, so we'll leave them empty
        # User will need to manually add them back if needed
        profile_yaml["agents"] = {}
        profile_yaml["contexts"] = []

        # Write profile.yaml
        (new_dir / "profile.yaml").write_text(yaml.dump(profile_yaml, default_flow_style=False))

    def get_profile(self, name: str) -> ProfileDetails:
        """Get detailed profile information.

        Reads from profile.yaml (source) if available, otherwise mount_plan.json.
        Returns structure suitable for editing.

        Args:
            name: Profile name

        Returns:
            Profile details

        Raises:
            FileNotFoundError: If profile not found
        """
        profile_dir = self.profiles_dir / name
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile not found: {name}")

        # Try to read from source YAML first (for editing)
        source_path = profile_dir / "profile.yaml"
        if source_path.exists():
            return self._load_from_source_yaml(source_path, name)

        # Fall back to mount_plan.json (legacy or registry profiles)
        mount_plan_path = profile_dir / "mount_plan.json"
        if mount_plan_path.exists():
            return self._load_from_mount_plan(mount_plan_path, name)

        raise FileNotFoundError(f"No profile.yaml or mount_plan.json found for: {name}")

    def _load_from_source_yaml(self, source_path: Path, name: str) -> ProfileDetails:
        """Load ProfileDetails from source profile.yaml.

        Preserves refs, configs, and structure for editing.

        Args:
            source_path: Path to profile.yaml
            name: Profile name

        Returns:
            Profile details with source structure preserved
        """
        import yaml

        try:
            source_data = yaml.safe_load(source_path.read_text())
            profile_info = source_data.get("profile", {})

            # Parse behaviors (modern format)
            behaviors = []
            for behavior in source_data.get("behaviors", []):
                if isinstance(behavior, dict):
                    behaviors.append(BehaviorRef(id=behavior.get("id", ""), source=behavior.get("source", "")))

            # Extract components as refs (not expanded)
            providers = []
            for provider in source_data.get("providers", []):
                providers.append(
                    ModuleConfig(
                        module=provider.get("id", ""), source=provider.get("source"), config=provider.get("config")
                    )
                )

            # Legacy format support - tools and hooks at top level
            # Modern format: these come from behaviors, so will be empty
            tools = []
            for tool_item in source_data.get("tools", []):
                tools.append(
                    ModuleConfig(
                        module=tool_item.get("id", ""), source=tool_item.get("source"), config=tool_item.get("config")
                    )
                )

            hooks = []
            for hook_item in source_data.get("hooks", []):
                hooks.append(
                    ModuleConfig(
                        module=hook_item.get("id", ""), source=hook_item.get("source"), config=hook_item.get("config")
                    )
                )

            # Extract agents as dict of refs (not content)
            # Modern format: agents come from behaviors, so will be empty
            agents = {}
            for agent_key, agent_ref in source_data.get("agents", {}).items():
                agents[agent_key] = agent_ref  # Keep as ref string

            # Extract contexts as refs
            contexts = {}
            for context_item in source_data.get("contexts", []):
                if isinstance(context_item, dict):
                    contexts[context_item.get("id")] = context_item.get("source")

            # Extract session config
            session_config = None
            orch_data = source_data.get("orchestrator", {})
            ctx_data = source_data.get("context", {})

            orchestrator = None
            if orch_data:
                orchestrator = ModuleConfig(
                    module=orch_data.get("id", ""), source=orch_data.get("source"), config=orch_data.get("config")
                )

            context_manager = None
            if ctx_data:
                context_manager = ModuleConfig(
                    module=ctx_data.get("id", ""), source=ctx_data.get("source"), config=ctx_data.get("config")
                )

            if orchestrator:
                session_config = SessionConfig(orchestrator=orchestrator, context_manager=context_manager)

            # Check if active
            active_profile = self.get_active_profile()
            is_active = active_profile == name

            return ProfileDetails(
                name=profile_info.get("name", name),
                schema_version=profile_info.get("schema_version", 3),
                version=profile_info.get("version", "1.0.0"),
                description=profile_info.get("description", ""),
                source=str(source_path),
                source_type="local",
                registry_id=None,
                source_uri=None,
                is_active=is_active,
                behaviors=behaviors,
                providers=providers,
                tools=tools,
                hooks=hooks,
                session=session_config,
                agents=agents,  # Dict of refs, not expanded content
                contexts=contexts,  # Dict of refs
                instruction=source_data.get("instructions", ""),
            )

        except Exception as e:
            logger.error(f"Failed to load profile from {source_path}: {e}")
            raise

    def _load_from_mount_plan(self, mount_plan_path: Path, name: str) -> ProfileDetails:
        """Load ProfileDetails from compiled mount_plan.json.

        This is the legacy path for profiles without source YAML.

        Args:
            mount_plan_path: Path to mount_plan.json
            name: Profile name

        Returns:
            Profile details
        """
        try:
            # Load mount plan
            mount_plan = json.loads(mount_plan_path.read_text())

            # Extract session config
            session_data = mount_plan.get("session", {})
            orchestrator_data = session_data.get("orchestrator")
            context_data = session_data.get("context")

            session_config = None
            if orchestrator_data:
                orch_config = ModuleConfig(
                    module=orchestrator_data.get("module", ""),
                    source=orchestrator_data.get("source"),
                    config=orchestrator_data.get("config"),
                )

                ctx_config = None
                if context_data:
                    ctx_config = ModuleConfig(
                        module=context_data.get("module", ""),
                        source=context_data.get("source"),
                        config=context_data.get("config"),
                    )

                session_config = SessionConfig(orchestrator=orch_config, context_manager=ctx_config)

            # Extract providers
            providers = []
            for prov_data in mount_plan.get("providers", []):
                providers.append(
                    ModuleConfig(
                        module=prov_data.get("module", ""),
                        source=prov_data.get("source"),
                        config=prov_data.get("config"),
                    )
                )

            # Extract tools
            tools = []
            for tool_data in mount_plan.get("tools", []):
                tools.append(
                    ModuleConfig(
                        module=tool_data.get("module", ""),
                        source=tool_data.get("source"),
                        config=tool_data.get("config"),
                    )
                )

            # Extract hooks
            hooks = []
            for hook_data in mount_plan.get("hooks", []):
                hooks.append(
                    ModuleConfig(
                        module=hook_data.get("module", ""),
                        source=hook_data.get("source"),
                        config=hook_data.get("config"),
                    )
                )

            # Extract agents (expanded content from mount_plan)
            agents = {}
            for agent_id, agent_data in mount_plan.get("agents", {}).items():
                agents[agent_id] = agent_data.get("content", "")

            # Check if active
            active_profile = self.get_active_profile()
            is_active = active_profile == name

            # Get profile metadata from settings
            settings = session_data.get("settings", {})
            profile_name = settings.get("profile_name", name)

            return ProfileDetails(
                name=profile_name,
                schema_version=3,
                version="1.0.0",
                description=f"Profile: {profile_name}",
                source=str(mount_plan_path.parent),
                source_type="local",
                registry_id=None,
                source_uri=None,
                is_active=is_active,
                behaviors=[],
                providers=providers,
                tools=tools,
                hooks=hooks,
                session=session_config,
                agents=agents,
                contexts={},
                instruction=None,
            )

        except Exception as e:
            logger.error(f"Failed to load profile from {mount_plan_path}: {e}")
            raise

    def update_profile(self, name: str, request: UpdateProfileRequest) -> ProfileDetails:
        """Update an existing profile.

        Args:
            name: Profile name
            request: Profile update request

        Returns:
            Updated profile details

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If validation fails or profile not editable
        """
        import yaml

        if not self.compilation_service:
            raise ValueError("ProfileCompilationService not available")

        profile_dir = self.profiles_dir / name

        # Verify profile exists
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile not found: {name}")

        # Verify profile is local (editable)
        if not (profile_dir / ".local").exists():
            raise ValueError(f"Profile is not editable: {name}. Only local profiles can be updated.")

        logger.info(f"Updating profile: {name}")

        # Get current profile to build updated YAML
        current = self.get_profile(name)

        # Build profile YAML structure with updates (source)
        profile_yaml: dict[str, object] = {
            "profile": {
                "name": name,
                "version": request.version or current.version,
                "description": request.description or current.description,
                "schema_version": 3,
            },
            "behaviors": [],
        }

        # Add orchestrator and context (use request values or keep current)
        orchestrator = (
            request.orchestrator
            if request.orchestrator is not None
            else (current.session.orchestrator if current.session else None)
        )
        if orchestrator:
            orch_config: dict[str, object] = {"id": orchestrator.module, "source": orchestrator.source}
            if orchestrator.config:
                orch_config["config"] = orchestrator.config
            profile_yaml["orchestrator"] = orch_config

        context = (
            request.context
            if request.context is not None
            else (current.session.context_manager if current.session else None)
        )
        if context:
            ctx_config: dict[str, object] = {"id": context.module, "source": context.source}
            if context.config:
                ctx_config["config"] = context.config
            profile_yaml["context"] = ctx_config

        # Add providers (use request values or keep current)
        providers = request.providers if request.providers is not None else current.providers
        if providers:
            profile_yaml["providers"] = [
                {"id": p.module, "source": p.source, "config": p.config or {}} for p in providers
            ]

        # Add tools (use request values or keep current)
        tools = request.tools if request.tools is not None else current.tools
        if tools:
            profile_yaml["tools"] = [{"id": t.module, "source": t.source, "config": t.config or {}} for t in tools]

        # Add hooks (use request values or keep current)
        hooks = request.hooks if request.hooks is not None else current.hooks
        if hooks:
            profile_yaml["hooks"] = [{"id": h.module, "source": h.source, "config": h.config or {}} for h in hooks]

        # Add agents (use request values or keep current)
        agents = request.agents if request.agents is not None else current.agents
        profile_yaml["agents"] = agents

        # Add contexts (use request values or keep current)
        contexts = request.contexts if request.contexts is not None else current.contexts
        if contexts:
            profile_yaml["contexts"] = [{"id": k, "source": v} for k, v in contexts.items()]

        # Add instruction (use request value or keep current)
        instruction = request.instruction if request.instruction is not None else current.instruction
        if instruction:
            profile_yaml["instructions"] = instruction

        # Write updated profile.yaml (source)
        (profile_dir / "profile.yaml").write_text(yaml.dump(profile_yaml, default_flow_style=False))

        # Build config YAML structure for compilation
        config_yaml: dict[str, object] = {"session": {}}

        # Add configurations for each component
        if orchestrator and orchestrator.config:
            if "session" not in config_yaml:
                config_yaml["session"] = {}
            config_yaml["session"]["orchestrator"] = orchestrator.config  # type: ignore

        if context and context.config:
            if "session" not in config_yaml:
                config_yaml["session"] = {}
            config_yaml["session"]["context"] = context.config  # type: ignore

        if providers:
            config_yaml["providers"] = {p.module: p.config or {} for p in providers}

        # Recompile the profile (creates mount_plan.json)
        self.compilation_service.compile_profile(profile_id=name, profile_yaml=profile_yaml, config_yaml=config_yaml)

        logger.info(f"Profile updated successfully: {name}")

        # Return the updated profile details
        return self.get_profile(name)

    def delete_profile(self, name: str) -> None:
        """Delete a profile.

        Args:
            name: Profile name to delete

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If trying to delete active profile or non-local profile
        """
        profile_dir = self.profiles_dir / name

        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile not found: {name}")

        # Check if profile is active
        active_profile = self.get_active_profile()
        if active_profile == name:
            raise ValueError(f"Cannot delete active profile: {name}. Deactivate it first.")

        # Check if profile is local (has .local marker or is in local directory)
        # For now, we allow deletion of any profile in the profiles directory
        # In the future, we might add a .local marker file to distinguish local vs registry profiles

        logger.info(f"Deleting profile: {name}")

        # Delete the profile directory
        import shutil

        shutil.rmtree(profile_dir)
        logger.info(f"Profile deleted: {name}")

    def compile_and_activate_profile(self, profile_id: str, profile_yaml: dict, config_yaml: dict) -> Path:
        """Compile and activate a profile.

        Args:
            profile_id: Profile identifier
            profile_yaml: Parsed profile YAML
            config_yaml: Parsed config YAML

        Returns:
            Path to compiled profile directory

        Raises:
            ValueError: If compilation fails or ProfileCompilationService not available
        """
        if not self.compilation_service:
            raise ValueError("ProfileCompilationService not available")

        logger.info(f"Compiling and activating profile: {profile_id}")

        # Compile the profile
        profile_path = self.compilation_service.compile_profile(
            profile_id=profile_id, profile_yaml=profile_yaml, config_yaml=config_yaml
        )

        # Activate the profile
        self.activate_profile(profile_id)

        logger.info(f"Profile compiled and activated: {profile_id}")
        return profile_path
