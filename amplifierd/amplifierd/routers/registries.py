"""Registry management API endpoints."""

import logging
from typing import Annotated

import yaml
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import Field
from pydantic import field_validator

from amplifier_library.services.registry_service import RegistryService

from ..dependencies import get_registry_service
from ..models.base import CamelCaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/registries", tags=["registries"])


class RegistryResponse(CamelCaseModel):
    """Registry information returned to clients."""

    id: str
    uri: str
    description: str = ""


class RegistryCreateRequest(CamelCaseModel):
    """Request to create a new registry."""

    uri: str = Field(..., description="URI to registry source (git+, file://, etc.)")
    description: str = Field("", description="Human-readable description")

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Validate URI format."""
        valid_prefixes = ("git+", "file://", "http://", "https://")
        if not any(v.startswith(prefix) for prefix in valid_prefixes):
            raise ValueError(f"URI must start with one of: {', '.join(valid_prefixes)}")
        return v


class RegistryUpdateRequest(CamelCaseModel):
    """Request to update registry description."""

    description: str


def generate_registry_id(uri: str) -> str:
    """Generate registry ID from URI.

    Examples:
        git+https://github.com/org/repo@main -> repo
        file:///path/to/registry -> registry
        https://example.com/registry -> registry
    """
    # Remove scheme prefix
    for prefix in ("git+https://", "git+http://", "https://", "http://", "file://"):
        if uri.startswith(prefix):
            uri = uri[len(prefix) :]
            break

    # Remove @ branch/tag suffix
    uri = uri.split("@")[0]

    # Extract last path component
    path = uri.rstrip("/").split("/")[-1]

    # Remove .git suffix if present
    if path.endswith(".git"):
        path = path[:-4]

    return path


def _load_registries_file(service: RegistryService) -> dict:
    """Load registries.yaml file."""
    if not service.registries_file.exists():
        service.ensure_default_registries()

    try:
        return yaml.safe_load(service.registries_file.read_text())
    except Exception as e:
        logger.error(f"Failed to load registries.yaml: {e}")
        raise HTTPException(status_code=500, detail="Failed to load registries file") from e


def _save_registries_file(service: RegistryService, data: dict) -> None:
    """Save registries.yaml file."""
    try:
        service.registries_file.write_text(yaml.safe_dump(data, default_flow_style=False, sort_keys=False))
    except Exception as e:
        logger.error(f"Failed to save registries.yaml: {e}")
        raise HTTPException(status_code=500, detail="Failed to save registries file") from e


@router.get("/", response_model=list[RegistryResponse])
async def list_registries(
    service: Annotated[RegistryService, Depends(get_registry_service)],
) -> list[RegistryResponse]:
    """List all registries.

    Args:
        service: Registry service instance

    Returns:
        List of registry information
    """
    registries = service.load_registries()
    return [RegistryResponse(id=reg.id, uri=reg.uri, description=reg.description) for reg in registries.values()]


@router.get("/{registry_id}", response_model=RegistryResponse)
async def get_registry(
    registry_id: str,
    service: Annotated[RegistryService, Depends(get_registry_service)],
) -> RegistryResponse:
    """Get specific registry.

    Args:
        registry_id: Registry identifier
        service: Registry service instance

    Returns:
        Registry information

    Raises:
        HTTPException: 404 if registry not found
    """
    registries = service.load_registries()

    if registry_id not in registries:
        raise HTTPException(status_code=404, detail=f"Registry not found: {registry_id}")

    reg = registries[registry_id]
    return RegistryResponse(id=reg.id, uri=reg.uri, description=reg.description)


@router.post("/", response_model=RegistryResponse, status_code=201)
async def create_registry(
    request: RegistryCreateRequest,
    service: Annotated[RegistryService, Depends(get_registry_service)],
) -> RegistryResponse:
    """Create new registry.

    Args:
        request: Registry creation request
        service: Registry service instance

    Returns:
        Created registry information

    Raises:
        HTTPException:
            - 400 for validation errors
            - 409 if registry with generated ID already exists
            - 500 for file errors
    """
    # Generate ID from URI
    registry_id = generate_registry_id(request.uri)

    # Load existing registries
    data = _load_registries_file(service)
    registries = data.get("registries", [])

    # Check if ID already exists
    if any(r.get("id") == registry_id for r in registries):
        raise HTTPException(status_code=409, detail=f"Registry with ID '{registry_id}' already exists")

    # Add new registry
    new_registry = {"id": registry_id, "uri": request.uri, "description": request.description}
    registries.append(new_registry)
    data["registries"] = registries

    # Save and reload
    _save_registries_file(service, data)
    service.load_registries(force_reload=True)

    logger.info(f"Created registry: {registry_id} ({request.uri})")

    return RegistryResponse(id=registry_id, uri=request.uri, description=request.description)


@router.patch("/{registry_id}", response_model=RegistryResponse)
async def update_registry(
    registry_id: str,
    request: RegistryUpdateRequest,
    service: Annotated[RegistryService, Depends(get_registry_service)],
) -> RegistryResponse:
    """Update registry description.

    Args:
        registry_id: Registry identifier
        request: Registry update request
        service: Registry service instance

    Returns:
        Updated registry information

    Raises:
        HTTPException:
            - 404 if registry not found
            - 500 for file errors
    """
    # Load existing registries
    data = _load_registries_file(service)
    registries = data.get("registries", [])

    # Find and update registry
    updated_reg = None
    for reg in registries:
        if reg.get("id") == registry_id:
            reg["description"] = request.description
            updated_reg = reg
            break

    if updated_reg is None:
        raise HTTPException(status_code=404, detail=f"Registry not found: {registry_id}")

    # Save and reload
    data["registries"] = registries
    _save_registries_file(service, data)
    service.load_registries(force_reload=True)

    logger.info(f"Updated registry: {registry_id}")

    return RegistryResponse(
        id=updated_reg["id"], uri=updated_reg["uri"], description=updated_reg.get("description", "")
    )


@router.delete("/{registry_id}", status_code=204)
async def delete_registry(
    registry_id: str,
    service: Annotated[RegistryService, Depends(get_registry_service)],
) -> None:
    """Delete registry.

    Args:
        registry_id: Registry identifier
        service: Registry service instance

    Raises:
        HTTPException:
            - 404 if registry not found
            - 409 if registry is "lakehouse" (default, cannot delete)
            - 500 for file errors
    """
    # Prevent deletion of default registry
    if registry_id == "lakehouse":
        raise HTTPException(status_code=409, detail="Cannot delete default 'lakehouse' registry")

    # Load existing registries
    data = _load_registries_file(service)
    registries = data.get("registries", [])

    # Find and remove registry
    original_count = len(registries)
    registries = [r for r in registries if r.get("id") != registry_id]

    if len(registries) == original_count:
        raise HTTPException(status_code=404, detail=f"Registry not found: {registry_id}")

    # Save and reload
    data["registries"] = registries
    _save_registries_file(service, data)
    service.load_registries(force_reload=True)

    logger.info(f"Deleted registry: {registry_id}")
