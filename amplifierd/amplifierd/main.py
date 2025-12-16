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

from .config.loader import load_config as load_daemon_config
from .routers import amplified_directories_router
from .routers import automations_router
from .routers import directories_router
from .routers import events_router
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

    # Initialize automation scheduler
    scheduler = None
    try:
        from amplifier_library.automations.manager import AutomationManager
        from amplifier_library.sessions.manager import SessionManager
        from amplifier_library.storage import get_state_dir

        from .services.automation_scheduler import AutomationScheduler

        state_dir = get_state_dir()
        automation_manager = AutomationManager(storage_dir=state_dir)
        session_manager = SessionManager(storage_dir=state_dir)

        scheduler = AutomationScheduler(
            automation_manager=automation_manager,
            session_manager=session_manager,
        )
        await scheduler.start()
        logger.info("Automation scheduler started")

        # Store scheduler in app state for access from routers
        app.state.automation_scheduler = scheduler
    except Exception as e:
        logger.error(f"Failed to start automation scheduler: {e}")
        # Don't fail startup, just log the error

    yield

    # Shutdown
    logger.info("Shutting down amplifierd daemon")

    # Stop automation scheduler
    if scheduler is not None:
        try:
            await scheduler.stop()
            logger.info("Automation scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop automation scheduler: {e}")


# Create FastAPI application
app = FastAPI(
    title="amplifierd",
    description="REST API daemon for amplifier-core with SSE streaming support",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware - origins configured in daemon.yaml
daemon_config = load_daemon_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=daemon_config.daemon.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"CORS enabled for origins: {daemon_config.daemon.cors_origins}")

# Include routers
app.include_router(amplified_directories_router)
app.include_router(automations_router)
app.include_router(directories_router)
app.include_router(events_router)
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


@app.get("/api/info")
async def info() -> dict[str, str | int]:
    """Get daemon and webapp location info.

    Returns:
        Dictionary with daemon/webapp paths and status
    """
    import os

    # Get daemon info
    daemon_path = str(Path(__file__).parent.parent)
    daemon_pid = os.getpid()

    # Get webapp info
    webapp_path = str(Path(__file__).parent.parent.parent / "webapp")
    webapp_url = "http://localhost:5173"

    return {
        "daemon_path": daemon_path,
        "daemon_pid": daemon_pid,
        "webapp_path": webapp_path,
        "webapp_url": webapp_url,
    }
