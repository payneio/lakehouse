"""Shared dependency factories for FastAPI endpoints.

These factories provide dependency injection for service instances,
ensuring proper initialization and resource management.
"""

from amplifier_library.services.registry_service import RegistryService
from amplifier_library.storage import get_cache_dir
from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir

from .services.profile_compilation import ProfileCompilationService
from .services.ref_resolution import RefResolutionService


def get_ref_resolution_service() -> RefResolutionService:
    """Get reference resolution service.

    Returns:
        RefResolutionService instance
    """
    state_dir = get_state_dir()
    return RefResolutionService(state_dir=state_dir)


def get_registry_service() -> RegistryService:
    """Get registry service (v3).

    Returns:
        RegistryService instance
    """
    share_dir = get_share_dir()
    registry_service = RegistryService(share_dir=share_dir)
    registry_service.ensure_default_registries()
    return registry_service


def get_profile_compilation_service() -> ProfileCompilationService:
    """Get profile compilation service (v3).

    Returns:
        ProfileCompilationService instance
    """
    share_dir = get_share_dir()
    cache_dir = get_cache_dir()
    ref_resolution = get_ref_resolution_service()
    registry_service = get_registry_service()

    return ProfileCompilationService(
        share_dir=share_dir,
        cache_dir=cache_dir,
        ref_resolution=ref_resolution,
        registry_service=registry_service,
    )
