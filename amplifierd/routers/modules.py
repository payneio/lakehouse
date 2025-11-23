"""Module discovery API endpoints."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel

from ..models import ModuleDetails
from ..models import ModuleInfo
from ..services.simple_module_service import SimpleModuleService

router = APIRouter(prefix="/api/v1/modules", tags=["modules"])


class ModuleSourceRequest(BaseModel):
    """Request body for module source operations."""

    source: str
    scope: str = "project"


def get_module_discovery_service() -> SimpleModuleService:
    """Get module discovery service instance.

    Returns:
        SimpleModuleService instance
    """
    from amplifier_library.storage import get_share_dir

    share_dir = get_share_dir()
    return SimpleModuleService(share_dir=share_dir)


@router.get("/", response_model=list[ModuleInfo])
async def list_modules(
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    type: Annotated[str | None, Query(description="Filter by module type")] = None,
) -> list[ModuleInfo]:
    """List modules with optional type filter.

    Args:
        service: Module discovery service instance
        type: Optional module type filter (provider, hook, tool, orchestrator)

    Returns:
        List of module information
    """
    return service.list_modules(type_filter=type)


@router.get("/providers", response_model=list[ModuleInfo])
async def list_providers(
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List provider modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of provider module information
    """
    return service.list_modules(type_filter="provider")


@router.get("/hooks", response_model=list[ModuleInfo])
async def list_hooks(
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List hook modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of hook module information
    """
    return service.list_modules(type_filter="hook")


@router.get("/tools", response_model=list[ModuleInfo])
async def list_tools(
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List tool modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of tool module information
    """
    return service.list_modules(type_filter="tool")


@router.get("/orchestrators", response_model=list[ModuleInfo])
async def list_orchestrators(
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> list[ModuleInfo]:
    """List orchestrator modules.

    Args:
        service: Module discovery service instance

    Returns:
        List of orchestrator module information
    """
    return service.list_modules(type_filter="orchestrator")


@router.get("/{module_id}", response_model=ModuleDetails)
async def get_module(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> ModuleDetails:
    """Get module details by ID.

    Args:
        module_id: Module identifier
        service: Module discovery service instance

    Returns:
        Module details

    Raises:
        HTTPException: 404 if module not found, 500 for other errors
    """
    try:
        return service.get_module(module_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{module_id}/sources", status_code=201)
async def add_module_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a module source override.

    Args:
        module_id: Module identifier
        request: Module source request
        service: Module discovery service instance

    Returns:
        Module source details

    Raises:
        HTTPException: 501 Not Implemented
    """
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.put("/{module_id}/sources", status_code=200)
async def update_module_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a module source override.

    Args:
        module_id: Module identifier
        request: Module source request
        service: Module discovery service instance

    Returns:
        Module source details

    Raises:
        HTTPException: 501 Not Implemented
    """
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.delete("/{module_id}/sources", status_code=200)
async def remove_module_source(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a module source override.

    Args:
        module_id: Module identifier
        scope: Configuration scope (user/project/local)
        service: Module discovery service instance

    Returns:
        Removal status

    Raises:
        HTTPException: 501 Not Implemented
    """
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


# Type-specific convenience endpoints


# PROVIDERS
@router.post("/providers/{module_id}/sources", status_code=201)
async def add_provider_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a provider module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.put("/providers/{module_id}/sources", status_code=200)
async def update_provider_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a provider module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.delete("/providers/{module_id}/sources", status_code=200)
async def remove_provider_source(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a provider module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


# HOOKS
@router.post("/hooks/{module_id}/sources", status_code=201)
async def add_hook_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a hook module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.put("/hooks/{module_id}/sources", status_code=200)
async def update_hook_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a hook module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.delete("/hooks/{module_id}/sources", status_code=200)
async def remove_hook_source(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a hook module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


# TOOLS
@router.post("/tools/{module_id}/sources", status_code=201)
async def add_tool_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add a tool module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.put("/tools/{module_id}/sources", status_code=200)
async def update_tool_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update a tool module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.delete("/tools/{module_id}/sources", status_code=200)
async def remove_tool_source(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove a tool module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


# ORCHESTRATORS
@router.post("/orchestrators/{module_id}/sources", status_code=201)
async def add_orchestrator_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Add an orchestrator module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.put("/orchestrators/{module_id}/sources", status_code=200)
async def update_orchestrator_source(
    module_id: str,
    request: ModuleSourceRequest,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
) -> dict[str, str]:
    """Update an orchestrator module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")


@router.delete("/orchestrators/{module_id}/sources", status_code=200)
async def remove_orchestrator_source(
    module_id: str,
    service: Annotated[SimpleModuleService, Depends(get_module_discovery_service)],
    scope: str = "project",
) -> dict[str, bool]:
    """Remove an orchestrator module source override."""
    raise HTTPException(status_code=501, detail="Module source management not implemented in SimpleModuleService")
