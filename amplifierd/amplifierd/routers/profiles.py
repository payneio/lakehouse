"""Profile management API endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import Field

from amplifier_library.storage.paths import get_bundles_dir

from ..models import ProfileDetails
from ..models import ProfileInfo
from ..models.base import CamelCaseModel
from ..models.profiles import CreateProfileRequest
from ..models.profiles import UpdateProfileRequest
from ..services.bundle_profile_service import BundleProfileService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


class CopyProfileRequest(CamelCaseModel):
    """Request body for copying a profile."""

    new_name: str = Field(pattern=r"^[a-z0-9-]+$", description="New profile name (kebab-case)")


def get_profile_service() -> BundleProfileService:
    """Get bundle profile service instance.

    Returns:
        BundleProfileService instance for managing bundles
    """
    bundles_dir = get_bundles_dir()
    return BundleProfileService(bundles_dir=bundles_dir)


@router.get("/", response_model=list[ProfileInfo])
async def list_profiles(
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> list[ProfileInfo]:
    """List all available bundles as profiles.

    Args:
        service: Bundle profile service instance

    Returns:
        List of profile information from bundle files
    """
    return service.list_profiles()


@router.post("/", response_model=ProfileDetails, status_code=201)
async def create_profile(
    request: CreateProfileRequest,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Create a new bundle.

    Args:
        request: Profile creation request with structured bundle data
        service: Bundle profile service instance

    Returns:
        Created bundle details

    Raises:
        HTTPException: 400 if bundle already exists or name is invalid
    """
    try:
        return service.create_bundle(bundle_data=request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{source_name}/copy", response_model=ProfileDetails, status_code=201)
async def copy_profile(
    source_name: str,
    request: CopyProfileRequest,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Copy a bundle with a new name.

    Args:
        source_name: Name of the bundle to copy
        request: Copy request with new name
        service: Bundle profile service instance

    Returns:
        ProfileDetails of the newly created bundle

    Raises:
        HTTPException: 404 if source not found, 400 if target exists or name invalid
    """
    try:
        return service.copy_bundle(source_name, request.new_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active", response_model=ProfileDetails | None)
async def get_active_profile(
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> ProfileDetails | None:
    """Get currently active profile.

    Note: Active profile tracking is not yet implemented for the bundle system.

    Args:
        service: Bundle profile service instance

    Returns:
        None (active profile not tracked in bundle system)
    """
    # Active profile tracking not implemented for bundles
    return None


@router.get("/{name}", response_model=ProfileDetails)
async def get_profile(
    name: str,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Get bundle profile details by name.

    Args:
        name: Profile name (e.g., "foundation/base")
        service: Bundle profile service instance

    Returns:
        Profile details

    Raises:
        HTTPException: 404 if bundle not found, 500 for other errors
    """
    try:
        return service.get_profile(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Profile not found: {name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{name}/content", response_model=dict)
async def get_profile_content(
    name: str,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> dict:
    """Get bundle content in structured format for editing.

    Args:
        name: Bundle name (e.g., "foundation/base")
        service: Bundle profile service instance

    Returns:
        Bundle data as structured dict matching Bundle dataclass fields

    Raises:
        HTTPException: 404 if bundle not found, 400 for parsing errors
    """
    try:
        return service.get_bundle_data(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {name}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse bundle: {exc}") from exc


@router.patch("/{name}", response_model=ProfileDetails)
async def update_profile(
    name: str,
    request: UpdateProfileRequest,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> ProfileDetails:
    """Update an existing bundle.

    Args:
        name: Profile name
        request: Update request with partial bundle data
        service: Bundle profile service instance

    Returns:
        Updated profile details

    Raises:
        HTTPException: 404 if bundle not found, 400 for other errors
    """
    try:
        # Only pass non-None fields to update
        return service.update_bundle(name, request.model_dump(exclude_none=True))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/active", status_code=200)
async def deactivate_profile(
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> dict[str, bool]:
    """Deactivate the current profile.

    Note: Active profile tracking is not yet implemented for the bundle system.

    Args:
        service: Bundle profile service instance

    Returns:
        Success status (always true since there's no active profile to deactivate)

    Raises:
        HTTPException: 500 for errors
    """
    # Active profile tracking not implemented for bundles
    return {"success": True}


@router.delete("/{name}", status_code=204)
async def delete_profile(
    name: str,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> None:
    """Delete a bundle.

    Args:
        name: Bundle name
        service: Bundle profile service instance

    Raises:
        HTTPException: 404 if bundle not found
    """
    try:
        service.delete_bundle(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/activate", status_code=200)
async def activate_profile(
    name: str,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> dict[str, str]:
    """Activate a profile by name.

    Note: Active profile tracking is not yet implemented for the bundle system.

    Args:
        name: Profile name
        service: Bundle profile service instance

    Returns:
        Activation status (always success since active profile not tracked)

    Raises:
        HTTPException: 404 if profile not found
    """
    # Check that bundle exists
    try:
        service.get_profile(name)
        return {"status": "activated", "name": name}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{profile_name}/compile", status_code=200)
async def compile_profile(
    profile_name: str,
    service: Annotated[BundleProfileService, Depends(get_profile_service)],
) -> dict[str, str]:
    """Compile a profile, resolving all refs and caching assets.

    Note: Bundle compilation happens automatically during bundle.prepare().
    This endpoint is not needed for the bundle system.

    Args:
        profile_name: Profile name
        service: Bundle profile service instance

    Returns:
        Compilation result

    Raises:
        HTTPException: 501 Not Implemented
    """
    raise HTTPException(
        status_code=501,
        detail="Profile compilation not needed for bundle system. Bundles are prepared automatically.",
    )
