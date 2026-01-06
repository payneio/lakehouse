"""Shared dependency factories for FastAPI endpoints.

These factories provide dependency injection for service instances,
ensuring proper initialization and resource management.
"""

from amplifier_library.services.registry_service import RegistryService
from amplifier_library.storage import get_share_dir


def get_registry_service() -> RegistryService:
    """Get registry service (v3).

    Returns:
        RegistryService instance
    """
    share_dir = get_share_dir()
    registry_service = RegistryService(share_dir=share_dir)
    registry_service.ensure_default_registries()
    return registry_service
