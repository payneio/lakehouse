"""Collection management API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel

from amplifier_library.storage import get_share_dir

from ..models import CollectionDetails
from ..models import CollectionInfo
from ..services.simple_collection_service import SimpleCollectionService

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


class MountCollectionRequest(BaseModel):
    """Request body for mounting a collection."""

    identifier: str
    source: str


def get_collection_service() -> SimpleCollectionService:
    """Get collection service instance.

    Returns:
        SimpleCollectionService instance
    """
    share_dir = get_share_dir()
    return SimpleCollectionService(share_dir=share_dir)


@router.get("/", response_model=list[CollectionInfo])
async def list_collections(
    service: Annotated[SimpleCollectionService, Depends(get_collection_service)],
) -> list[CollectionInfo]:
    """List all available collections.

    Args:
        service: Collection service instance

    Returns:
        List of collection information
    """
    return service.list_collections()


@router.get("/{identifier:path}", response_model=CollectionDetails)
async def get_collection(
    identifier: str,
    service: Annotated[SimpleCollectionService, Depends(get_collection_service)],
) -> CollectionDetails:
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
        return service.get_collection(identifier)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync")
async def sync_collections(
    service: Annotated[SimpleCollectionService, Depends(get_collection_service)],
    update: bool = False,
    sync_modules: bool = True,
) -> dict[str, dict[str, str] | dict[str, dict[str, str]]]:
    """Sync collections declared in collections.yaml.

    Reads collections.yaml and ensures all declared collections are installed.
    Clones missing collections and optionally updates existing ones.
    Also syncs modules for all profiles in synced collections.

    Args:
        service: Collection service instance
        update: Whether to update (git pull) existing collections
        sync_modules: Whether to sync modules for profiles in synced collections

    Returns:
        Sync status for each collection and module sync results

    Raises:
        HTTPException: 500 for sync errors
    """
    try:
        results = service.sync_collections(update=update)

        module_results = {}
        if sync_modules:
            from ..services.simple_profile_service import SimpleProfileService

            share_dir = get_share_dir()
            data_dir = get_share_dir()
            profile_service = SimpleProfileService(share_dir=share_dir, data_dir=data_dir)

            for collection_name, status in results.items():
                if status in ["synced", "updated"]:
                    profiles = profile_service.list_profiles()
                    collection_profiles = [
                        p.name for p in profiles if p.source.startswith(f"{collection_name}/profiles/")
                    ]

                    for profile_name in collection_profiles:
                        try:
                            profile_module_results = profile_service.sync_profile_modules(profile_name)
                            if profile_module_results:
                                module_results[f"{collection_name}/{profile_name}"] = profile_module_results
                        except Exception as e:
                            module_results[f"{collection_name}/{profile_name}"] = {"error": str(e)}

        return {"collections": results, "modules": module_results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}") from exc


@router.post("/", status_code=201)
async def mount_collection(
    request: MountCollectionRequest,
    service: Annotated[SimpleCollectionService, Depends(get_collection_service)],
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
    service: Annotated[SimpleCollectionService, Depends(get_collection_service)],
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
