"""Main FastAPI application for lakehoused daemon.

This module creates and configures the FastAPI application that exposes
the Lakehouse data platform via REST API with SSE streaming.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lakehoused.config.settings import load_config

from .auth import auth_required as _auth_required
from .auth import verify_token as _verify_token
from .config.loader import load_config as load_daemon_config
from .routers import assistants_router
from .routers import auth_router
from .routers import automations_router
from .routers import events_router
from .routers import files_router
from .routers import messages_router
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
            default_assistant = os.getenv("LAKEHOUSED_DEFAULT_ASSISTANT", "foundation/foundation")
            logger.info(f"Auto-creating root project with assistant: {default_assistant}")

            project_service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant=default_assistant,
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

    # Initialize the opencode server registry (pooled `opencode serve` processes).
    opencode_servers = None
    try:
        from lakehoused.config.settings import load_config as load_settings
        from lakehoused.opencode import OpencodeServerRegistry

        settings = load_settings()
        opencode_servers = OpencodeServerRegistry(
            opencode_bin=settings.opencode_bin,
            max_servers=settings.opencode_max_servers,
        )
        app.state.opencode_servers = opencode_servers
        logger.info(
            "Initialized OpencodeServerRegistry (bin=%s, max_servers=%d)",
            settings.opencode_bin,
            settings.opencode_max_servers,
        )
    except Exception as e:
        logger.error(f"Failed to initialize opencode server registry: {e}")
        app.state.opencode_servers = None

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
            opencode_servers=opencode_servers,
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

    # Shut down opencode servers
    if opencode_servers is not None:
        try:
            await opencode_servers.close_all()
            logger.info("Closed all opencode servers")
        except Exception as e:
            logger.error(f"Failed to close opencode servers: {e}")


# Create FastAPI application
app = FastAPI(
    title="lakehoused",
    description="REST API daemon for the Lakehouse data platform with SSE streaming support",
    version="0.1.0",
    lifespan=lifespan,
)

# Password gate middleware. Enforces a session token on /api/ requests when a
# password is configured in secrets.yaml. Registered BEFORE the CORS middleware
# below so that CORS remains the outermost layer (Starlette runs the last-added
# middleware first), ensuring 401 responses still carry CORS headers and the
# browser can read them.
_AUTH_EXEMPT_PREFIXES = ("/api/v1/auth/",)
# Exact paths that must stay public (e.g. liveness/readiness probes).
_AUTH_EXEMPT_PATHS = frozenset({"/api/v1/health"})


@app.middleware("http")
async def password_gate(request: Request, call_next):
    """Require a valid session token for API requests when auth is enabled."""
    path = request.url.path

    # Only gate API routes; static SPA assets are public (data lives behind the API).
    if not path.startswith("/api/"):
        return await call_next(request)

    # Always allow auth endpoints, health checks, and CORS preflight requests.
    if request.method == "OPTIONS" or path in _AUTH_EXEMPT_PATHS or path.startswith(_AUTH_EXEMPT_PREFIXES):
        return await call_next(request)

    # No password configured -> gate disabled, pass everything through.
    if not _auth_required():
        return await call_next(request)

    # Accept the token from the Authorization header or a `token` query param.
    # EventSource (SSE) cannot set headers, so streaming endpoints pass it in
    # the query string instead.
    token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
    if token is None:
        token = request.query_params.get("token")

    if not _verify_token(token):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    return await call_next(request)


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
app.include_router(assistants_router)
app.include_router(auth_router)
app.include_router(automations_router)
app.include_router(events_router)
app.include_router(files_router)
app.include_router(messages_router)
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
