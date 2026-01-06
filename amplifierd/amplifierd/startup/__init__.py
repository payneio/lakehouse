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
    """Handle startup updates for bundle-based system.

    Note: With bundles, there's no need for registry updates or profile syncing.
    Bundles are loaded on-demand from the bundles directory.

    Args:
        config: Startup configuration
    """
    if not config.check_cache_on_startup:
        logger.info("Startup updates disabled")
        return

    logger.info("Bundle system: No startup syncing required")
    logger.info("Bundles will be loaded on-demand from bundles directory")
