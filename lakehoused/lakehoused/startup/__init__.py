"""Startup handlers for lakehoused daemon.

Handles startup tasks.
"""

import logging

from lakehoused.config.models import StartupConfig

logger = logging.getLogger(__name__)


async def handle_startup_updates(config: StartupConfig) -> None:
    """Handle startup updates.

    Args:
        config: Startup configuration
    """
    if not config.check_cache_on_startup:
        logger.info("Startup cache check disabled")
        return

    logger.info("Startup: Assistant system uses on-demand loading via LakehouseOpencodeManager")
