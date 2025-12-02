"""Collection management API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel

from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir

from ..models import CollectionInfo
from ..services.collection_service import CollectionService

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


class MountCollectionRequest(BaseModel):
    """Request body for mounting a collection."""

    identifier: str
    source: str


def get_collection_service() -> CollectionService:
    """Get collection service instance.

    Returns:
        CollectionService instance with profile discovery/compilation
    """
    from amplifier_library.storage.paths import get_profiles_dir

    from ..services.profile_compilation import ProfileCompilationService
    from ..services.profile_discovery import ProfileDiscoveryService
    from ..services.ref_resolution import RefResolutionService

    share_dir = get_share_dir()
    state_dir = get_state_dir()

    # Create profile services for auto-discovery and compilation
    profiles_dir = get_profiles_dir()
    discovery_service = ProfileDiscoveryService(cache_dir=profiles_dir)

    ref_resolution = RefResolutionService(state_dir=state_dir)
    compilation_service = ProfileCompilationService(share_dir=share_dir, ref_resolution=ref_resolution)

    return CollectionService(
        share_dir=share_dir,
        discovery_service=discovery_service,
        compilation_service=compilation_service,
    )


@router.get("", response_model=list[CollectionInfo])
@router.get("/", response_model=list[CollectionInfo])
async def list_collections(
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> list[CollectionInfo]:
    """List all available collections.

    Args:
        service: Collection service instance

    Returns:
        List of collection information
    """
    return service.list_collections()


@router.get("/{identifier:path}", response_model=CollectionInfo)
async def get_collection(
    identifier: str,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> CollectionInfo:
    """Get collection details by identifier.

    Args:
        identifier: Collection identifier
        service: Collection service instance

    Returns:
        Collection details

    Raises:
        HTTPException: 404 if collection not found, 500 for other errors
    """
    try:
        return service.get_collection_info(identifier)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/", status_code=201)
async def mount_collection(
    request: MountCollectionRequest,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> dict[str, str]:
    """Mount a collection.

    Args:
        request: Mount collection request
        service: Collection service instance

    Returns:
        Mount status

    Raises:
        HTTPException: 409 if already mounted, 400 for invalid source, 500 for other errors
    """
    try:
        service.mount_collection(request.identifier, request.source)
        return {"status": "mounted", "identifier": request.identifier, "source": request.source}
    except ValueError as exc:
        if "already" in str(exc).lower():
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to mount collection: {str(exc)}") from exc


@router.delete("/{identifier:path}", status_code=200)
async def unmount_collection(
    identifier: str,
    service: Annotated[CollectionService, Depends(get_collection_service)],
) -> dict[str, bool]:
    """Unmount a collection.

    Args:
        identifier: Collection identifier
        service: Collection service instance

    Returns:
        Unmount status

    Raises:
        HTTPException: 404 if collection not found, 500 for other errors
    """
    try:
        service.unmount_collection(identifier)
        return {"success": True}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to unmount collection: {str(exc)}") from exc
