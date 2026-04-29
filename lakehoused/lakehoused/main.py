"""Main FastAPI application for lakehoused daemon.

This module creates and configures the FastAPI application that exposes
the amplifier_library via REST API with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from lakehoused.config.settings import load_config

from .config.loader import load_config as load_daemon_config
from .routers import automations_router
from .routers import bundles_router
from .routers import events_router
from .routers import files_router
from .routers import messages_router
from .routers import modules_router
from .routers import mount_plans_router
from .routers import projects_router
from .routers import sessions_router
from .routers import settings_router
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
    logger.info(f"Starting lakehoused daemon on {config.host}:{config.port}")
    logger.info(f"Data root: {config.data_path}")

    # Auto-create root project on startup
    try:
        import os

        from .models.projects import ProjectCreate
        from .services.project_service import ProjectService

        root_dir = Path(config.data_path)
        project_service = ProjectService(root_dir)

        # Ensure root is a project
        if not project_service.is_project("."):
            default_bundle = os.getenv("LAKEHOUSED_DEFAULT_BUNDLE", "foundation/foundation")
            logger.info(f"Auto-creating root project with profile: {default_bundle}")

            project_service.create(
                ProjectCreate(
                    relative_path=".",
                    default_bundle=default_bundle,
                    metadata={
                        "name": "root",
                        "description": "Root project (auto-created)",
                        "auto_created": True,
                    },
                    create_marker=True,
                )
            )
            logger.info("Root project created successfully")
        else:
            logger.info("Root directory is already a project")
    except Exception as e:
        logger.error(f"Failed to auto-create root project: {e}")
        # Don't fail startup, just log the error

    # Handle cache updates based on startup configuration
    daemon_config = None
    try:
        from .config.loader import load_config as load_daemon_config
        from .startup import handle_startup_updates

        daemon_config = load_daemon_config()
        await handle_startup_updates(daemon_config.startup)
    except Exception as e:
        logger.error(f"Startup cache handling failed: {e}")
        # Don't fail startup, just log the error

    # Initialize module resolver (Foundation's BundleModuleResolver)
    try:
        from amplifier_foundation.modules.activator import ModuleActivator

        from lakehoused.storage.paths import get_cache_dir

        cache_dir = get_cache_dir()
        activator = ModuleActivator(cache_dir=cache_dir, install_deps=True)

        # Create an empty resolver - PreparedBundles will populate it with their module paths
        # For now, we just need the activator functionality for git-based modules
        from amplifier_foundation.bundle import BundleModuleResolver

        resolver = BundleModuleResolver(module_paths={}, activator=activator)

        # Store resolver in app state for access from routers
        app.state.module_resolver = resolver
        logger.info(f"Initialized BundleModuleResolver with cache_dir={cache_dir}")
    except Exception as e:
        logger.error(f"Failed to initialize module resolver: {e}")
        resolver = None  # Ensure resolver is always bound

    # Initialize automation scheduler
    scheduler = None
    try:
        from lakehoused.automations.manager import AutomationManager
        from lakehoused.sessions.manager import SessionManager
        from lakehoused.storage import get_state_dir

        from .services.automation_scheduler import AutomationScheduler

        state_dir = get_state_dir()
        automation_manager = AutomationManager(storage_dir=state_dir)
        session_manager = SessionManager(storage_dir=state_dir)

        # Get timezone from daemon config (already loaded above)
        scheduler_timezone = daemon_config.daemon.timezone if daemon_config else "UTC"

        scheduler = AutomationScheduler(
            automation_manager=automation_manager,
            session_manager=session_manager,
            timezone=scheduler_timezone,
            module_resolver=resolver,
        )
        await scheduler.start()
        logger.info(f"Automation scheduler started with timezone: {scheduler_timezone}")

        # Store scheduler in app state for access from routers
        app.state.automation_scheduler = scheduler
    except Exception as e:
        logger.error(f"Failed to start automation scheduler: {e}")
        # Don't fail startup, just log the error

    yield

    # Shutdown
    logger.info("Shutting down lakehoused daemon")

    # Stop automation scheduler
    if scheduler is not None:
        try:
            await scheduler.stop()
            logger.info("Automation scheduler stopped")
        except Exception as e:
            logger.error(f"Failed to stop automation scheduler: {e}")


# Create FastAPI application
app = FastAPI(
    title="lakehoused",
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
app.include_router(automations_router)
app.include_router(bundles_router)
app.include_router(events_router)
app.include_router(files_router)
app.include_router(messages_router)
app.include_router(modules_router)
app.include_router(mount_plans_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(settings_router)
app.include_router(status_router)
app.include_router(stream_router)


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
    webapp_url = "http://localhost:7777"

    return {
        "daemon_path": daemon_path,
        "daemon_pid": daemon_pid,
        "webapp_path": webapp_path,
        "webapp_url": webapp_url,
    }


# --- Static file serving for bundled SPA ---
# When webapp_dist/ exists (production/Nixpacks build), serve the frontend
# from FastAPI. In dev mode (no webapp_dist/), this is skipped entirely.
#
# Search order:
#   1. Next to installed package (pip install with package-data)
#   2. Relative to working directory (simple deploys)
#   3. Source tree layout (Nixpacks: vite build runs AFTER pip install,
#      so webapp_dist lands in the source tree, not the installed package)
_webapp_dist_candidates = [
    Path(__file__).parent / "webapp_dist",
    Path("webapp_dist"),
    Path(__file__).resolve().parent / "webapp_dist",
]
# In Nixpacks, the source tree lives under /app/ and the install step copies
# the package to /opt/venv/..., but vite build writes to /app/lakehoused/lakehoused/webapp_dist.
# If NIXPACKS=1 or the /app/ source tree exists, check there too.
_nixpacks_source = Path("/app/lakehoused/lakehoused/webapp_dist")
if _nixpacks_source not in _webapp_dist_candidates:
    _webapp_dist_candidates.append(_nixpacks_source)

_webapp_dist = next((p for p in _webapp_dist_candidates if p.exists() and p.is_dir()), None)

if _webapp_dist is not None:
    logger.info("Serving bundled webapp from %s", _webapp_dist)

    # Serve static assets (JS, CSS, images) directly
    app.mount("/assets", StaticFiles(directory=_webapp_dist / "assets"), name="static-assets")

    # Catch-all: serve index.html for all non-API routes (SPA client-side routing)
    @app.get("/{path:path}")
    async def serve_spa(request: Request, path: str) -> Response:
        """Serve the SPA index.html for all non-API routes.

        Skips /api/ paths so unmatched API requests return proper 404s
        instead of the SPA HTML.
        """
        if path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": f"Not found: /{path}"})
        assert _webapp_dist is not None  # guarded by outer if
        file_path = _webapp_dist / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_webapp_dist / "index.html")
