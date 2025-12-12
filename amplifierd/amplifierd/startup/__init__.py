"""Startup handlers for amplifierd daemon (v3).

Handles registry updates and profile source syncing on daemon startup.
"""

import logging
import shutil
from pathlib import Path

import yaml

from amplifierd.config.models import StartupConfig

logger = logging.getLogger(__name__)


def save_profile_source(
    profile_id: str,
    profile_yaml: dict,
    config_yaml: dict,
    source_dir: Path,
    dest_dir: Path,
) -> None:
    """Save profile source YAML and copy component assets.

    Args:
        profile_id: Profile identifier
        profile_yaml: Profile YAML dictionary
        config_yaml: Config YAML dictionary (unused in current implementation)
        source_dir: Source directory from registry
        dest_dir: Destination profiles directory
    """
    profile_dir = dest_dir / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    # Save profile.yaml
    profile_yaml_path = profile_dir / "profile.yaml"
    profile_yaml_path.write_text(yaml.dump(profile_yaml, default_flow_style=False))
    logger.info(f"Saved profile source: {profile_yaml_path}")

    # Copy component assets if they exist in source
    if source_dir.is_dir():
        for item in source_dir.iterdir():
            if item.is_dir() and item.name in [
                "behaviors",
                "session",
                "contexts",
                "agents",
                "hooks",
                "tools",
                "providers",
            ]:
                dest_item = profile_dir / item.name
                if dest_item.exists():
                    shutil.rmtree(dest_item)
                shutil.copytree(item, dest_item)
                logger.debug(f"Copied {item.name}/ to profile")


async def handle_startup_updates(config: StartupConfig) -> None:
    """Handle v3 startup updates: registries + profile source syncing.

    V3 startup process:
    1. Refresh registries (fetch latest if git+ URIs)
    2. Load profiles.yaml (list of profiles to keep synced)
    3. Sync profile sources (profile.yaml + component assets) from registries

    Note: Profile compilation happens during session creation, not startup.

    Args:
        config: Startup configuration
    """
    if not config.check_cache_on_startup:
        logger.info("V3 startup updates disabled")
        return

    logger.info("V3 startup: Checking registries and profiles...")

    try:
        from amplifier_library.services.registry_service import RegistryService
        from amplifier_library.storage import get_cache_dir
        from amplifier_library.storage import get_share_dir
        from amplifierd.services.ref_resolution import RefResolutionService

        # STEP 1: Refresh registries
        share_dir = get_share_dir()
        registry_service = RegistryService(share_dir=share_dir)

        # Ensure registries.yaml exists
        registry_service.ensure_default_registries()

        # Load registries
        registries = registry_service.load_registries(force_reload=True)
        logger.info(f"Loaded {len(registries)} registries: {', '.join(registries.keys())}")

        # TODO: Refresh git-based registries (pull latest)
        # For now, they're cached - could add refresh logic here

        # STEP 2: Load profiles.yaml (list of profiles to sync from registries)
        profiles_config_path = get_share_dir() / "profiles.yaml"

        if not profiles_config_path.exists():
            logger.info("No profiles.yaml found - skipping profile sync")
            logger.info(f"Create {profiles_config_path} with 'profiles:' list to sync profiles on startup")
            return

        # Load profiles list
        profiles_config = yaml.safe_load(profiles_config_path.read_text())
        profiles_to_sync = profiles_config.get("profiles", [])

        if not profiles_to_sync:
            logger.info("profiles.yaml exists but has no profiles listed")
            return

        logger.info(f"Found {len(profiles_to_sync)} profiles to sync")

        # STEP 3: Parse profile entries (format: - profile-id: amp://registry/path)
        profile_refs = {}
        for item in profiles_to_sync:
            if isinstance(item, dict):
                # Dict format: {profile-id: amp://URI}
                for profile_id, amp_uri in item.items():
                    profile_refs[profile_id] = amp_uri

        if not profile_refs:
            logger.info("No valid profile references in profiles.yaml")
            return

        logger.info(f"Parsed {len(profile_refs)} profile references")

        # STEP 3.5: Delete existing registry profiles (will be rebuilt)
        profiles_dir = share_dir / "profiles"
        logger.info("Deleting existing registry profiles for rebuild...")
        if profiles_dir.exists():
            for profile_dir in profiles_dir.iterdir():
                if not profile_dir.is_dir():
                    continue

                # Check if this is a local profile (don't delete)
                # Local profiles are marked with .local file
                local_marker = profile_dir / ".local"
                if local_marker.exists():
                    logger.debug(f"Skipping local profile: {profile_dir.name}")
                    continue

                # This is a registry profile - delete it
                logger.info(f"Deleting registry profile for rebuild: {profile_dir.name}")
                shutil.rmtree(profile_dir)

        logger.info("Registry profiles deleted, will rebuild from registries")

        # STEP 4: Fetch and save profile sources from registry
        ref_resolution = RefResolutionService(state_dir=get_cache_dir())
        synced_count = 0

        for profile_id, amp_uri in profile_refs.items():
            # Fetch profile source from registry
            try:
                logger.info(f"Fetching profile '{profile_id}' from {amp_uri}")

                # Resolve amp:// URI to registry path
                resolved_uri = registry_service.resolve_amp_uri(amp_uri)

                # Fetch profile directory from registry
                profile_source_dir = ref_resolution.resolve_ref(resolved_uri)

                # Detect format: single file or directory
                if profile_source_dir.is_file():
                    # Modern format: single YAML file contains everything
                    logger.debug(f"Loading profile from flat file: {profile_source_dir}")
                    profile_yaml = yaml.safe_load(profile_source_dir.read_text())
                    config_yaml = {}  # No separate config in flat format

                elif profile_source_dir.is_dir():
                    # Legacy format: directory with profile.yaml + config.yaml
                    logger.debug(f"Loading profile from directory: {profile_source_dir}")
                    profile_yaml_path = profile_source_dir / "profile.yaml"
                    config_yaml_path = profile_source_dir / "config.yaml"

                    if not profile_yaml_path.exists():
                        logger.warning(f"profile.yaml not found in {profile_source_dir}")
                        continue

                    profile_yaml = yaml.safe_load(profile_yaml_path.read_text())

                    # config.yaml is optional in directory format
                    if config_yaml_path.exists():
                        config_yaml = yaml.safe_load(config_yaml_path.read_text())
                    else:
                        logger.debug(f"No config.yaml for '{profile_id}', using defaults")
                        config_yaml = {}
                else:
                    logger.error(f"Profile path is neither file nor directory: {profile_source_dir}")
                    continue

                # Save profile source (no compilation yet)
                logger.info(f"Saving profile source '{profile_id}'...")
                save_profile_source(profile_id, profile_yaml, config_yaml, profile_source_dir, profiles_dir)

                # Compile profile to fetch and resolve all assets
                try:
                    from amplifierd.services.profile_compilation import ProfileCompilationService

                    compilation_service = ProfileCompilationService(
                        share_dir=share_dir,
                        cache_dir=get_cache_dir(),
                        ref_resolution=ref_resolution,
                        registry_service=registry_service,
                    )

                    logger.info(f"Compiling assets for '{profile_id}'...")
                    compiled_path = compilation_service.compile_profile(profile_id, profile_yaml, config_yaml)

                    # Remove mount_plan.json (created per-session, not part of profile source)
                    mount_plan_path = compiled_path / "mount_plan.json"
                    if mount_plan_path.exists():
                        mount_plan_path.unlink()
                        logger.debug("Removed mount_plan.json (created per-session)")

                    logger.info(f"✓ Profile '{profile_id}' assets compiled")

                except Exception as e:
                    logger.warning(f"Failed to compile profile assets for '{profile_id}': {e}")
                    # Continue anyway - profile.yaml exists, assets can be compiled later

                logger.info(f"✓ Profile '{profile_id}' synced to {profile_dir}")
                synced_count += 1

            except Exception as e:
                logger.error(f"Failed to sync profile '{profile_id}': {e}")

        logger.info(f"Startup complete: {synced_count} synced, {len(profile_refs) - synced_count} failed")

    except Exception as e:
        logger.error(f"Failed to handle startup updates: {e}", exc_info=True)
        # Don't fail startup on cache update errors
