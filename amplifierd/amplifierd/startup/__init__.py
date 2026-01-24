"""Startup handlers for amplifierd daemon.

Handles bundle registry parsing and startup tasks.
"""

import logging

from amplifierd.config.models import StartupConfig

from .bundle_sync import ensure_bundles_file
from .bundle_sync import parse_bundles_file

logger = logging.getLogger(__name__)

# Module-level cache for parsed bundles from BUNDLES.txt
# These are git+ URIs that Foundation will resolve via git cloning
_REGISTRY_BUNDLES: dict[str, str] = {}


def get_registry_bundles() -> dict[str, str]:
    """Get parsed bundles from BUNDLES.txt.

    Returns a copy of the cached bundle name->URI mappings.
    These should be passed to LakehouseBundleManager for registration
    with Foundation's BundleRegistry.

    Returns:
        Dict mapping bundle name to git+ URI.
    """
    return _REGISTRY_BUNDLES.copy()


async def handle_startup_updates(config: StartupConfig) -> None:
    """Handle startup updates including bundle registry parsing.

    Parses BUNDLES.txt on daemon startup to populate the registry cache.
    LakehouseBundleManager instances use this to register bundles with Foundation.

    Args:
        config: Startup configuration
    """
    # Always parse BUNDLES.txt on startup (independent of cache check setting)
    await _sync_system_bundles()

    if not config.check_cache_on_startup:
        logger.info("Startup cache check disabled")
        return

    logger.info("Startup: Bundle system uses on-demand loading via LakehouseBundleManager")


async def _sync_system_bundles() -> None:
    """Parse BUNDLES.txt and populate the registry cache.

    Creates BUNDLES.txt with defaults if it doesn't exist, then parses
    all bundle name->URI mappings for use by LakehouseBundleManager.

    Note: This does NOT download files. Foundation handles git cloning/caching
    when bundles are actually loaded, preserving full repo structure.
    """
    from lakehouse_library.storage.paths import get_bundles_dir

    bundles_dir = get_bundles_dir()  # ~/.amplifierd/share/bundles/
    bundles_file = bundles_dir / "BUNDLES.txt"

    # Create BUNDLES.txt with defaults if it doesn't exist
    ensure_bundles_file(bundles_file)

    # Parse bundles and populate the module-level cache
    try:
        registry_bundles = parse_bundles_file(bundles_file)

        # Update the module-level cache
        _REGISTRY_BUNDLES.clear()
        _REGISTRY_BUNDLES.update(registry_bundles)

        if registry_bundles:
            logger.info(f"Parsed {len(registry_bundles)} bundles from BUNDLES.txt")
        else:
            logger.warning("No bundles found in BUNDLES.txt")
    except Exception as e:
        logger.error(f"Failed to parse BUNDLES.txt: {e}")
        # Don't fail startup, just log the error
