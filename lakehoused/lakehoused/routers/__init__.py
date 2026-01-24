"""API routers for lakehoused daemon.

This module contains FastAPI routers for all API endpoints.
"""

from .automations import router as automations_router
from .bundles import router as bundles_router
from .events import router as events_router
from .files import router as files_router
from .messages import router as messages_router
from .modules import router as modules_router
from .mount_plans import router as mount_plans_router
from .projects import router as projects_router
from .sessions import router as sessions_router
from .settings import router as settings_router
from .status import router as status_router
from .stream import router as stream_router

__all__ = [
    "automations_router",
    "bundles_router",
    "events_router",
    "files_router",
    "messages_router",
    "modules_router",
    "mount_plans_router",
    "projects_router",
    "sessions_router",
    "settings_router",
    "status_router",
    "stream_router",
]
