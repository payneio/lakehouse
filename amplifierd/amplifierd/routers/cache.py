"""Thin HTTP wrapper around amplifier_library.cache services.

Architecture: This router contains ONLY HTTP handling.
All business logic is in amplifier_library.cache.
"""

import logging
from typing import Annotated

from amplifier_library.cache import AllCacheStatus
from amplifier_library.cache import AllUpdateResult
from amplifier_library.cache import CollectionCacheStatus
from amplifier_library.cache import CollectionUpdateResult
from amplifier_library.cache import ProfileCacheStatus
from amplifier_library.cache import ProfileUpdateResult
from amplifier_library.cache import StatusService
from amplifier_library.cache import UpdateService
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from ..dependencies import get_status_service
from ..dependencies import get_update_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


# =============================================================================
# Status Endpoints
# =============================================================================


@router.get("/status", response_model=AllCacheStatus)
async def get_all_cache_status(
    service: Annotated[StatusService, Depends(get_status_service)],
) -> AllCacheStatus:
    """Get cache status for all collections and profiles."""
    try:
        return service.get_all_status()
    except Exception as exc:
        logger.error(f"Failed to get cache status: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/status/collections/{identifier}", response_model=CollectionCacheStatus)
async def get_collection_cache_status(
    identifier: str,
    service: Annotated[StatusService, Depends(get_status_service)],
) -> CollectionCacheStatus:
    """Get cache status for one collection with all its profiles."""
    try:
        status = service.get_collection_status(identifier)
        if not status:
            raise HTTPException(status_code=404, detail=f"Collection not found: {identifier}")
        return status
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get collection status: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/status/profiles/{collection_id}/{profile_name}", response_model=ProfileCacheStatus)
async def get_profile_cache_status(
    collection_id: str,
    profile_name: str,
    service: Annotated[StatusService, Depends(get_status_service)],
) -> ProfileCacheStatus:
    """Get cache status for one profile."""
    try:
        profile_id = f"{collection_id}/{profile_name}"
        status = service.get_profile_status(collection_id, profile_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        return status
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get profile status: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# =============================================================================
# Update Endpoints
# =============================================================================


@router.post("/update", response_model=AllUpdateResult)
async def update_all_collections(
    service: Annotated[UpdateService, Depends(get_update_service)],
    check_only: bool = Query(False, description="Only check what would be updated, don't update"),
    force: bool = Query(False, description="Force update even if cache is fresh"),
) -> AllUpdateResult:
    """Update cache for all collections."""
    try:
        return await service.update_all(
            check_only=check_only,
            force=force,
        )
    except Exception as exc:
        logger.error(f"Failed to update all collections: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/update/collections/{identifier}", response_model=CollectionUpdateResult)
async def update_collection(
    identifier: str,
    service: Annotated[UpdateService, Depends(get_update_service)],
    check_only: bool = Query(False, description="Only check what would be updated, don't update"),
    force: bool = Query(False, description="Force update even if cache is fresh"),
) -> CollectionUpdateResult:
    """Update cache for one collection."""
    try:
        result = await service.update_collection(
            collection_id=identifier,
            check_only=check_only,
            force=force,
        )
        if not result.success and "not found" in result.message.lower():
            raise HTTPException(status_code=404, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update collection {identifier}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.post("/update/profiles/{collection_id}/{profile_name}", response_model=ProfileUpdateResult)
async def update_profile(
    collection_id: str,
    profile_name: str,
    service: Annotated[UpdateService, Depends(get_update_service)],
    check_only: bool = Query(False, description="Only check what would be updated, don't update"),
    force: bool = Query(False, description="Force update even if cache is fresh"),
) -> ProfileUpdateResult:
    """Update cache for one profile."""
    try:
        profile_id = f"{collection_id}/{profile_name}"
        result = await service.update_profile(
            collection_id=collection_id,
            profile_id=profile_id,
            check_only=check_only,
            force=force,
        )
        if not result.success and "not found" in result.message.lower():
            raise HTTPException(status_code=404, detail=result.message)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update profile {collection_id}/{profile_name}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
