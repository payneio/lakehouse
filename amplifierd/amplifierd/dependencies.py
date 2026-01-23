"""Shared dependency factories for FastAPI endpoints.

These factories provide dependency injection for service instances,
ensuring proper initialization and resource management.
"""

from amplifier_library.storage import get_share_dir

from .services.module_service import ModuleService


def get_module_service() -> ModuleService:
    """Get module service.

    Returns:
        ModuleService instance
    """
    share_dir = get_share_dir()
    return ModuleService(share_dir=share_dir)
