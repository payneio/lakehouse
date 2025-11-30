"""Profile management API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import Field

from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir
from amplifier_library.storage.paths import get_profiles_dir

from ..models import ProfileDetails
from ..models import ProfileInfo
from ..models.base import CamelCaseModel
from ..models.profiles import CreateProfileRequest
from ..models.profiles import UpdateProfileRequest
from ..services.profile_compilation import ProfileCompilationService
from ..services.profile_discovery import ProfileDiscoveryService
from ..services.profile_service import ProfileService
from ..services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


class CopyProfileRequest(CamelCaseModel):
    """Request body for copying a profile."""

    new_name: str = Field(pattern=r"^[a-z0-9-]+$", description="New profile name (kebab-case)")


def get_profile_service() -> ProfileService:
    """Get profile service instance with new services.

    Returns:
        ProfileService instance with discovery and compilation services
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


@router.post("/", response_model=ProfileDetails, status_code=201)
async def create_profile(
    request: CreateProfileRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Create a new profile in local collection.

    Args:
        request: Profile creation request
        service: Profile service instance

    Returns:
        Created profile details

    Raises:
        HTTPException:
            - 409 if profile already exists
            - 400 for validation errors
            - 500 for other errors
    """
    try:
        return service.create_profile(request)
    except ValueError as exc:
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to create profile: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/{source_name}/copy", response_model=ProfileDetails, status_code=201)
async def copy_profile(
    source_name: str,
    request: CopyProfileRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Copy a profile to local collection with a new name.

    Creates a copy of an existing profile in the local collection. The source
    profile can be from any collection. All fields are copied including providers,
    tools, hooks, session configuration, and system instruction.

    Args:
        source_name: Name of the profile to copy
        request: Copy request with new name
        service: Profile service instance

    Returns:
        ProfileDetails of the newly created profile

    Raises:
        HTTPException:
            - 404 if source profile not found
            - 400 for validation errors (invalid name format)
            - 409 if profile with new name already exists
            - 500 for other errors
    """
    try:
        return service.copy_profile(source_name, request.new_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Source profile not found: {source_name}") from exc
    except ValueError as exc:
        # Check if it's a conflict (already exists) or validation error
        if "already exists" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to copy profile {source_name} to {request.new_name}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


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


@router.patch("/{name}", response_model=ProfileDetails)
async def update_profile(
    name: str,
    request: UpdateProfileRequest,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Update an existing local profile.

    Args:
        name: Profile name
        request: Update request
        service: Profile service instance

    Returns:
        Updated profile details

    Raises:
        HTTPException:
            - 404 if profile not found
            - 403 if profile not in local collection
            - 400 for validation errors
            - 500 for other errors
    """
    try:
        return service.update_profile(name, request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        if "Cannot modify" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to update profile {name}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


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


@router.delete("/{name}", status_code=204)
async def delete_profile(
    name: str,
    service: Annotated[ProfileService, Depends(get_profile_service)],
) -> None:
    """Delete a local profile.

    Args:
        name: Profile name
        service: Profile service instance

    Raises:
        HTTPException:
            - 404 if profile not found
            - 403 if profile not in local collection
            - 409 if profile is currently active
            - 500 for other errors
    """
    try:
        service.delete_profile(name)
        logger.info(f"Deleted profile: {name}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        if "Cannot modify" in str(exc) or "not local" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if "active" in str(exc).lower():
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to delete profile {name}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


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
