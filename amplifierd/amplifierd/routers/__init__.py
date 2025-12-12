"""API routers for amplifierd daemon.

This module contains FastAPI routers for all API endpoints.
"""

from .amplified_directories import router as amplified_directories_router
from .automations import router as automations_router
from .directories import router as directories_router
from .events import router as events_router
from .messages import router as messages_router
from .modules import router as modules_router
from .mount_plans import router as mount_plans_router
from .profiles import router as profiles_router
from .registries import router as registries_router
from .sessions import router as sessions_router
from .status import router as status_router
from .stream import router as stream_router

__all__ = [
    "amplified_directories_router",
    "automations_router",
    "directories_router",
    "events_router",
    "sessions_router",
    "messages_router",
    "status_router",
    "profiles_router",
    "registries_router",
    "modules_router",
    "mount_plans_router",
    "stream_router",
]
