"""Startup handlers for lakehoused daemon.

Handles bundle registry initialization and startup tasks.
"""

import logging

from lakehoused.config.models import StartupConfig
from lakehoused.services.bundle_registry import BundleRegistryService

logger = logging.getLogger(__name__)


def get_registry_bundles() -> dict[str, str]:
    """Get parsed bundles from BUNDLES.txt.

    Returns a copy of the cached bundle name->URI mappings.
    These should be passed to LakehouseBundleManager for registration
    with Foundation's BundleRegistry.

    Returns:
        Dict mapping bundle name to git+ URI.
    """
    return BundleRegistryService.get_instance().get_entries()


def get_bundle_registry_service() -> BundleRegistryService:
    """Get the singleton BundleRegistryService instance.

    Returns:
        The BundleRegistryService instance.
    """
    return BundleRegistryService.get_instance()


async def handle_startup_updates(config: StartupConfig) -> None:
    """Handle startup updates including bundle registry initialization.

    Initializes the BundleRegistryService on daemon startup.
    The service loads BUNDLES.txt and creates it with defaults if needed.

    Args:
        config: Startup configuration
    """
    # Initialize the bundle registry service (loads BUNDLES.txt)
    # The service is a singleton, so this just ensures it's initialized
    service = BundleRegistryService.get_instance()
    logger.info(f"Bundle registry initialized with {len(service.get_entries())} bundles")

    if not config.check_cache_on_startup:
        logger.info("Startup cache check disabled")
        return

    logger.info("Startup: Bundle system uses on-demand loading via LakehouseBundleManager")
