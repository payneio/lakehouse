"""Main FastAPI application for amplifierd daemon.

This module creates and configures the FastAPI application that exposes
the amplifier_library via REST API with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amplifier_library.config.loader import load_config

from .routers import collections_router
from .routers import messages_router
from .routers import modules_router
from .routers import profiles_router
from .routers import sessions_router
from .routers import status_router

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
    logger.info(f"Data root: {config.amplifierd_root}")

    # Sync collections on startup with automatic profile discovery
    try:
        from amplifier_library.storage import get_share_dir
        from amplifier_library.storage import get_state_dir
        from amplifier_library.storage.paths import get_profiles_dir

        from .services.collection_service import CollectionService
        from .services.profile_compilation import ProfileCompilationService
        from .services.profile_discovery import ProfileDiscoveryService
        from .services.ref_resolution import RefResolutionService

        share_dir = get_share_dir()
        state_dir = get_state_dir()

        profiles_dir = get_profiles_dir()
        discovery_service = ProfileDiscoveryService(cache_dir=profiles_dir)

        ref_resolution = RefResolutionService(state_dir=state_dir)
        compilation_service = ProfileCompilationService(
            share_dir=share_dir,
            ref_resolution=ref_resolution,
        )

        collection_service = CollectionService(
            share_dir=share_dir,
            discovery_service=discovery_service,
            compilation_service=compilation_service,
        )

        results = collection_service.sync_collections(update=True)

        synced_count = sum(1 for status in results.values() if status == "synced")
        if synced_count > 0:
            logger.info(f"Synced {synced_count} collection(s) on startup: {list(results.keys())}")
    except Exception as e:
        logger.warning(f"Collection sync on startup failed: {e}")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions_router)
app.include_router(messages_router)
app.include_router(status_router)
app.include_router(profiles_router)
app.include_router(collections_router)
app.include_router(modules_router)


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
