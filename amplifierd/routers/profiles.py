"""Profile management API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir
from amplifier_library.storage.paths import get_profiles_dir

from ..models import ProfileDetails
from ..models import ProfileInfo
from ..services.profile_compilation import ProfileCompilationService
from ..services.profile_discovery import ProfileDiscoveryService
from ..services.profile_service import ProfileService
from ..services.ref_resolution import RefResolutionService

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def get_profile_service() -> ProfileService:
    """Get profile service instance with new services.

    Returns:
        SimpleProfileService instance with discovery and compilation services
    """
    share_dir = get_share_dir()
    data_dir = get_share_dir()
    state_dir = get_state_dir()

    discovery_service = ProfileDiscoveryService(cache_dir=get_profiles_dir())

    ref_resolution = RefResolutionService(state_dir=state_dir)
    compilation_service = ProfileCompilationService(share_dir=share_dir, ref_resolution=ref_resolution)

    return ProfileService(
        share_dir=share_dir,
        data_dir=data_dir,
        discovery_service=discovery_service,
        compilation_service=compilation_service,
    )


@router.get("/", response_model=list[ProfileInfo])
async def list_profiles(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> list[ProfileInfo]:
    """List all available profiles.

    Args:
        service: Profile service instance

    Returns:
        List of profile information
    """
    return service.list_profiles()


@router.get("/active", response_model=ProfileDetails | None)
async def get_active_profile(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails | None:
    """Get currently active profile.

    Args:
        service: Profile service instance

    Returns:
        Active profile details or None
    """
    return service.get_active_profile()


@router.get("/{name}", response_model=ProfileDetails)
async def get_profile(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Get profile details by name.

    Args:
        name: Profile name
        service: Profile service instance

    Returns:
        Profile details

    Raises:
        HTTPException: 404 if profile not found, 500 for other errors
    """
    try:
        return service.get_profile(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{name}/activate", status_code=200)
async def activate_profile(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, str]:
    """Activate a profile by name.

    Args:
        name: Profile name
        service: Profile service instance

    Returns:
        Activation status

    Raises:
        HTTPException: 404 if profile not found, 500 for other errors
    """
    try:
        service.activate_profile(name)
        return {"status": "activated", "name": name}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to activate profile: {str(exc)}") from exc


@router.delete("/active", status_code=200)
async def deactivate_profile(
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, bool]:
    """Deactivate the current profile.

    Args:
        service: Profile service instance

    Returns:
        Deactivation status

    Raises:
        HTTPException: 500 for errors
    """
    try:
        service.deactivate_profile()
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate profile: {str(exc)}") from exc


@router.post("/{name}/sync-modules", status_code=200)
async def sync_profile_modules(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, dict[str, str]]:
    """Sync modules for a profile.

    Resolves and caches all module dependencies declared in the profile with sources.

    Args:
        name: Profile name
        service: Profile service instance

    Returns:
        Sync results mapping module_id to status

    Raises:
        HTTPException: 404 if profile not found, 500 for other errors
    """
    try:
        results = service.sync_profile_modules(name)
        return {"results": results}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to sync modules: {str(exc)}") from exc


@router.post("/{collection_id}/{profile_name}/compile", status_code=200)
async def compile_profile(
    collection_id: str,
    profile_name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> dict[str, str]:
    """Compile a profile, resolving all refs and caching assets.

    Args:
        collection_id: Collection identifier
        profile_name: Profile name
        service: Profile service instance

    Returns:
        Compilation result with compiled profile path

    Raises:
        HTTPException: 404 if profile not found, 500 for compilation errors
    """
    try:
        compiled_path = service.compile_and_activate_profile(collection_id, profile_name)
        return {
            "status": "compiled",
            "collection_id": collection_id,
            "profile_name": profile_name,
            "compiled_path": str(compiled_path),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {collection_id}/{profile_name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Compilation failed: {str(exc)}") from exc
