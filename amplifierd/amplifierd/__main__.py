"""Entry point for running amplifierd daemon.

This module provides the CLI entry point for starting the daemon.
"""

import logging
import sys

import uvicorn

from .config.loader import load_config

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the amplifierd daemon.

    Loads configuration and starts the uvicorn server.
    """
    try:
        # Load configuration
        config = load_config()

        # Configure logging level
        log_level = config.daemon.log_level.lower()

        # Start uvicorn server
        uvicorn.run(
            "amplifierd.main:app",
            host=config.daemon.host,
            port=config.daemon.port,
            log_level=log_level,
            workers=config.daemon.workers,
        )

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start daemon: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
