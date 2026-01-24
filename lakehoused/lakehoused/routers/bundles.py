"""Bundle management API endpoints."""

import logging

from fastapi import APIRouter
from fastapi import HTTPException

from lakehoused.models.bundles import BundleDetails
from lakehoused.models.bundles import BundleListItem
from lakehoused.models.bundles import BundleSource
from lakehoused.models.bundles import CopyBundleRequest
from lakehoused.models.bundles import CreateBundleRequest
from lakehoused.models.bundles import ResolvedBundle
from lakehoused.models.bundles import UpdateBundleRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])


def _get_bundle_manager():
    """Get the bundle manager instance."""
    from lakehouse_library.bundles import LakehouseBundleManager

    from ..startup import get_registry_bundles

    return LakehouseBundleManager(registry_bundles=get_registry_bundles())


@router.get("/")
async def list_bundles() -> list[BundleListItem]:
    """List all available bundles with summary information.

    Returns list of bundles with their names, descriptions, and quick stats.
    Bundles are loaded from ~/.lakehoused/bundles/ (user) and
    ~/.lakehoused/share/bundles/ (system).

    Returns:
        List of BundleListItem with name, source, and module counts.
    """
    bundle_manager = _get_bundle_manager()
    bundles_info = bundle_manager.list_bundles_with_info()

    result = []
    for info in bundles_info:
        # Load bundle to get details
        try:
            details = await bundle_manager.get_bundle_details(info.name)
            result.append(
                BundleListItem(
                    name=info.name,
                    version=details.get("version", "1.0.0"),
                    description=details.get("description"),
                    source=info.source,
                    path=str(info.path),
                    provider_count=details.get("provider_count", 0),
                    tool_count=details.get("tool_count", 0),
                    hook_count=details.get("hook_count", 0),
                    agent_count=details.get("agent_count", 0),
                    includes=details.get("includes", []),
                )
            )
        except Exception as e:
            logger.warning(f"Failed to load bundle details for {info.name}: {e}")
            # Return minimal info on error
            result.append(
                BundleListItem(
                    name=info.name,
                    source=info.source,
                    path=str(info.path),
                )
            )

    return result


@router.get("/{name}/")
async def get_bundle(name: str) -> BundleDetails:
    """Get detailed information about a specific bundle.

    Args:
        name: Bundle name.

    Returns:
        BundleDetails with full bundle information.

    Raises:
        404: If bundle not found.
    """
    bundle_manager = _get_bundle_manager()

    try:
        details = await bundle_manager.get_bundle_details(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return BundleDetails(**details)


@router.get("/{name}/resolved")
async def get_resolved_bundle(name: str) -> ResolvedBundle:
    """Get the resolved/flattened view of a bundle with source tracking.

    This shows what will actually run when the bundle is used, with tracking
    of which bundle contributed each component (for override visualization).

    Args:
        name: Bundle name.

    Returns:
        ResolvedBundle with flattened modules and source tracking.

    Raises:
        404: If bundle not found.
    """
    bundle_manager = _get_bundle_manager()

    try:
        resolved = await bundle_manager.get_resolved_bundle(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ResolvedBundle(**resolved)


@router.get("/{name}/source")
async def get_bundle_source(name: str) -> BundleSource:
    """Get the raw source content of a bundle file.

    Args:
        name: Bundle name.

    Returns:
        BundleSource with raw file content.

    Raises:
        404: If bundle not found.
    """
    bundle_manager = _get_bundle_manager()

    try:
        content, path, file_format = bundle_manager.get_bundle_source_content(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return BundleSource(
        name=name,
        content=content,
        path=path,
        format=file_format,
    )


@router.post("/")
async def create_bundle(request: CreateBundleRequest) -> BundleListItem:
    """Create a new user bundle.

    Args:
        request: Bundle creation request with name and optional base bundle.

    Returns:
        BundleListItem for the new bundle.

    Raises:
        400: If bundle name already exists.
    """
    bundle_manager = _get_bundle_manager()

    try:
        info = await bundle_manager.create_bundle(
            name=request.name,
            base_bundle=request.base_bundle,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BundleListItem(
        name=info.name,
        source=info.source,
        path=str(info.path),
    )


@router.post("/{name}/copy")
async def copy_bundle(name: str, request: CopyBundleRequest) -> BundleListItem:
    """Copy a bundle to user bundles.

    Args:
        name: Source bundle name.
        request: Copy request with new bundle name.

    Returns:
        BundleListItem for the new bundle.

    Raises:
        404: If source bundle not found.
        400: If new name already exists.
    """
    bundle_manager = _get_bundle_manager()

    try:
        info = await bundle_manager.copy_bundle(name, request.new_name)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return BundleListItem(
        name=info.name,
        source=info.source,
        path=str(info.path),
    )


@router.put("/{name}/")
async def update_bundle(name: str, request: UpdateBundleRequest) -> BundleListItem:
    """Update a user bundle's content.

    Args:
        name: Bundle name.
        request: Update request with new content.

    Returns:
        BundleListItem for the updated bundle.

    Raises:
        404: If bundle not found.
        403: If trying to update a system bundle.
    """
    bundle_manager = _get_bundle_manager()

    info = bundle_manager.get_bundle_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {name}")

    if info.source != "user":
        raise HTTPException(status_code=403, detail=f"Cannot update system bundle: {name}")

    try:
        bundle_manager.update_bundle(name, request.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return BundleListItem(
        name=info.name,
        source=info.source,
        path=str(info.path),
    )


@router.delete("/{name}/")
async def delete_bundle(name: str) -> dict[str, str]:
    """Delete a user bundle.

    Args:
        name: Bundle name.

    Returns:
        Success message.

    Raises:
        404: If bundle not found.
        403: If trying to delete a system bundle.
    """
    bundle_manager = _get_bundle_manager()

    info = bundle_manager.get_bundle_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {name}")

    if info.source != "user":
        raise HTTPException(status_code=403, detail=f"Cannot delete system bundle: {name}")

    try:
        bundle_manager.delete_bundle(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"Bundle deleted: {name}"}
