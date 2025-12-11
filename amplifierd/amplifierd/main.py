"""Main FastAPI application for amplifierd daemon.

This module creates and configures the FastAPI application that exposes
the amplifier_library via REST API with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amplifier_library.config.loader import load_config

from .routers import amplified_directories_router
from .routers import directories_router
from .routers import messages_router
from .routers import modules_router
from .routers import mount_plans_router
from .routers import profiles_router
from .routers import registries_router
from .routers import sessions_router
from .routers import status_router
from .routers import stream_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application instance
    """
    # Startup
    config = load_config()
    logger.info(f"Starting amplifierd daemon on {config.host}:{config.port}")
    logger.info(f"Data root: {config.data_path}")

    # Auto-amplify root directory on startup
    try:
        import os

        from .models.amplified_directories import AmplifiedDirectoryCreate
        from .services.amplified_directory_service import AmplifiedDirectoryService

        root_dir = Path(config.data_path)
        amplified_service = AmplifiedDirectoryService(root_dir)

        # Ensure root is amplified
        if not amplified_service.is_amplified("."):
            default_profile = os.getenv("AMPLIFIERD_DEFAULT_PROFILE", "foundation/foundation")
            logger.info(f"Auto-amplifying root directory with profile: {default_profile}")

            amplified_service.create(
                AmplifiedDirectoryCreate(
                    relative_path=".",
                    default_profile=default_profile,
                    metadata={
                        "name": "root",
                        "description": "Root amplified directory (auto-created)",
                        "auto_created": True,
                    },
                    create_marker=True,
                )
            )
            logger.info("Root directory amplified successfully")
        else:
            logger.info("Root directory already amplified")
    except Exception as e:
        logger.error(f"Failed to auto-amplify root directory: {e}")
        # Don't fail startup, just log the error

    # Handle cache updates based on startup configuration
    try:
        from .config.loader import load_config as load_daemon_config
        from .startup import handle_startup_updates

        daemon_config = load_daemon_config()
        await handle_startup_updates(daemon_config.startup)
    except Exception as e:
        logger.error(f"Startup cache handling failed: {e}")
        # Don't fail startup, just log the error

    yield

    # Shutdown
    logger.info("Shutting down amplifierd daemon")


# Create FastAPI application
app = FastAPI(
    title="amplifierd",
    description="REST API daemon for amplifier-core with SSE streaming support",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Alternative port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(amplified_directories_router)
app.include_router(directories_router)
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(status_router)
app.include_router(profiles_router)
app.include_router(registries_router)
app.include_router(modules_router)
app.include_router(mount_plans_router)
app.include_router(stream_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint.

    Returns:
        Welcome message with API information
    """
    return {
        "name": "amplifierd",
        "version": "0.1.0",
        "description": "REST API daemon for amplifier-core",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
