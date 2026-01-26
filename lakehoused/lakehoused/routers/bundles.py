"""Bundle management API endpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi import HTTPException

from lakehoused.models.bundles import AddRegistryBundleRequest
from lakehoused.models.bundles import BundleDetails
from lakehoused.models.bundles import BundleListItem
from lakehoused.models.bundles import BundleSource
from lakehoused.models.bundles import CopyBundleRequest
from lakehoused.models.bundles import CreateBundleRequest
from lakehoused.models.bundles import RenameBundleRequest
from lakehoused.models.bundles import ResolvedBundle
from lakehoused.models.bundles import UpdateBundleRequest

if TYPE_CHECKING:
    from lakehouse_library.bundles import LakehouseBundleManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])

# Singleton bundle manager to preserve Foundation registry state across requests.
# This ensures that after adding a bundle, subsequent views use the same
# registry instance with all loaded bundle state (includes, namespace paths, etc.)
_bundle_manager: LakehouseBundleManager | None = None


def _get_bundle_manager() -> LakehouseBundleManager:
    """Get the singleton bundle manager instance.

    Creates the manager on first call, reuses it for subsequent calls.
    This preserves Foundation's BundleRegistry cache state across API requests,
    which is necessary for proper include resolution after adding bundles.
    """
    global _bundle_manager
    if _bundle_manager is None:
        from lakehouse_library.bundles import LakehouseBundleManager

        from ..startup import get_registry_bundles

        _bundle_manager = LakehouseBundleManager(registry_bundles=get_registry_bundles())
    return _bundle_manager


def _reset_bundle_manager() -> None:
    """Reset the singleton bundle manager.

    Call this when the bundle registry has been modified externally
    and needs to be reloaded from scratch.
    """
    global _bundle_manager
    _bundle_manager = None


async def _build_bundle_list_item(bundle_manager, info) -> BundleListItem:
    """Build a complete BundleListItem with full details.

    Args:
        bundle_manager: LakehouseBundleManager instance.
        info: BundleInfo for the bundle.

    Returns:
        BundleListItem with all fields populated.
    """
    # Normalize source: "registry" bundles are non-editable like "system" bundles
    source = "user" if info.source == "user" else "system"

    try:
        details = await bundle_manager.get_bundle_details(info.name)
        return BundleListItem(
            name=info.name,
            version=details.get("version", "1.0.0"),
            description=details.get("description"),
            source=source,
            path=str(info.path),
            provider_count=details.get("provider_count", 0),
            tool_count=details.get("tool_count", 0),
            hook_count=details.get("hook_count", 0),
            agent_count=details.get("agent_count", 0),
            includes=details.get("includes", []),
        )
    except Exception as e:
        logger.warning(f"Failed to load bundle details for {info.name}: {e}")
        # Return minimal info on error
        return BundleListItem(
            name=info.name,
            source=source,
            path=str(info.path),
        )


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
        item = await _build_bundle_list_item(bundle_manager, info)
        result.append(item)

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
        content, path, file_format = await bundle_manager.get_bundle_source_content(name)
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

    return await _build_bundle_list_item(bundle_manager, info)


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

    return await _build_bundle_list_item(bundle_manager, info)


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

    return await _build_bundle_list_item(bundle_manager, info)


@router.post("/{name}/rename")
async def rename_bundle(name: str, request: RenameBundleRequest) -> BundleListItem:
    """Rename a user bundle.

    Args:
        name: Current bundle name.
        request: Rename request with new name.

    Returns:
        BundleListItem for the renamed bundle.

    Raises:
        404: If bundle not found.
        403: If trying to rename a system bundle.
        400: If new name already exists.
    """
    from lakehoused.models.bundles import RenameBundleRequest as RenameBundleRequestModel

    # Cast to proper type (workaround for forward reference)
    _ = RenameBundleRequestModel
    bundle_manager = _get_bundle_manager()

    try:
        info = bundle_manager.rename_bundle(name, request.new_name)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        if "system bundle" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return await _build_bundle_list_item(bundle_manager, info)


@router.delete("/{name}/")
async def delete_bundle(name: str) -> dict[str, str]:
    """Delete a bundle (user or registry).

    User bundles are deleted from the filesystem.
    Registry bundles are removed from BUNDLES.txt.

    Args:
        name: Bundle name.

    Returns:
        Success message.

    Raises:
        404: If bundle not found.
    """
    from lakehoused.services.bundle_registry import BundleRegistryService

    bundle_manager = _get_bundle_manager()

    info = bundle_manager.get_bundle_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Bundle not found: {name}")

    if info.source == "user":
        # Delete user bundle from filesystem
        try:
            bundle_manager.delete_bundle(name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"message": f"Bundle deleted: {name}"}

    # Remove registry bundle using the service
    service = BundleRegistryService.get_instance()
    try:
        service.remove(name, bundle_manager)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"message": f"Registry bundle removed: {name}"}


@router.post("/registry")
async def add_registry_bundle(request: AddRegistryBundleRequest) -> dict[str, str]:
    """Add a bundle from a git URL to the registry (BUNDLES.txt).

    This adds an entry to ~/.lakehoused/share/bundles/BUNDLES.txt,
    registers with Foundation, and fetches/caches the bundle immediately
    so it's ready to use.

    Args:
        request: Registry bundle request with name and git_url.

    Returns:
        Success message.

    Raises:
        400: If bundle name already exists, URL is invalid, or fetch fails.
    """
    from lakehoused.services.bundle_registry import BundleRegistryService

    service = BundleRegistryService.get_instance()
    bundle_manager = _get_bundle_manager()

    # Add to BUNDLES.txt and register with Foundation
    try:
        service.add(request.name, request.git_url, bundle_manager)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch/cache the bundle immediately
    try:
        await bundle_manager.register_and_fetch_bundle(request.name, request.git_url)
    except ValueError as e:
        # Fetch failed - remove from registry to keep consistent
        import contextlib

        with contextlib.suppress(Exception):
            service.remove(request.name, bundle_manager)
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"Added and cached registry bundle: {request.name}"}


@router.delete("/registry/{name}")
async def remove_registry_bundle(name: str) -> dict[str, str]:
    """Remove a bundle from the registry (BUNDLES.txt).

    Args:
        name: Bundle name to remove.

    Returns:
        Success message.

    Raises:
        404: If bundle not found in registry.
    """
    from lakehoused.services.bundle_registry import BundleRegistryService

    service = BundleRegistryService.get_instance()
    bundle_manager = _get_bundle_manager()

    try:
        service.remove(name, bundle_manager)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"message": f"Removed registry bundle: {name}"}
