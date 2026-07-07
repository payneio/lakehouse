"""API routers for lakehoused daemon.

This module contains FastAPI routers for all API endpoints.
"""

from .assistants import router as assistants_router
from .auth import router as auth_router
from .automations import router as automations_router
from .events import router as events_router
from .files import router as files_router
from .messages import router as messages_router
from .projects import router as projects_router
from .sessions import router as sessions_router
from .settings import router as settings_router
from .status import router as status_router
from .stream import router as stream_router

__all__ = [
    "assistants_router",
    "auth_router",
    "automations_router",
    "events_router",
    "files_router",
    "messages_router",
    "projects_router",
    "sessions_router",
    "settings_router",
    "status_router",
    "stream_router",
]
