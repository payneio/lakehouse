"""Assistant management API endpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi import HTTPException

from lakehoused.models.assistants import AssistantDetails
from lakehoused.models.assistants import AssistantListItem
from lakehoused.models.assistants import AssistantSource
from lakehoused.models.assistants import CopyAssistantRequest
from lakehoused.models.assistants import CreateAssistantRequest
from lakehoused.models.assistants import RenameAssistantRequest
from lakehoused.models.assistants import ResolvedAssistant
from lakehoused.models.assistants import UpdateAssistantRequest

if TYPE_CHECKING:
    from lakehoused.opencode import LakehouseOpencodeManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/assistants", tags=["assistants"])

# Singleton assistant manager (opencode manifest catalog).
_assistant_manager: LakehouseOpencodeManager | None = None


def _get_assistant_manager() -> LakehouseOpencodeManager:
    """Get the singleton assistant manager (opencode manifest catalog)."""
    global _assistant_manager
    if _assistant_manager is None:
        from lakehoused.config.settings import load_config
        from lakehoused.opencode import LakehouseOpencodeManager

        settings = load_config()
        _assistant_manager = LakehouseOpencodeManager(settings.opencode_assistants_path or None)
    return _assistant_manager


def _reset_assistant_manager() -> None:
    """Reset the singleton assistant manager (e.g. after manifests change on disk)."""
    global _assistant_manager
    _assistant_manager = None


async def _build_assistant_list_item(assistant_manager, info) -> AssistantListItem:
    """Build a complete AssistantListItem with full details.

    Args:
        assistant_manager: LakehouseOpencodeManager instance.
        info: AssistantInfo for the assistant.

    Returns:
        AssistantListItem with all fields populated.
    """
    # Normalize source: "registry" assistants are non-editable like "system" assistants
    source = "user" if info.source == "user" else "system"

    try:
        details = await assistant_manager.get_assistant_details(info.name)
        return AssistantListItem(
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
        logger.warning(f"Failed to load assistant details for {info.name}: {e}")
        # Return minimal info on error
        return AssistantListItem(
            name=info.name,
            source=source,
            path=str(info.path),
        )


@router.get("/")
async def list_assistants() -> list[AssistantListItem]:
    """List all available assistants with summary information.

    Returns list of assistants with their names, descriptions, and quick stats.

    Returns:
        List of AssistantListItem with name, source, and module counts.
    """
    assistant_manager = _get_assistant_manager()
    assistants_info = assistant_manager.list_assistants()

    result = []
    for info in assistants_info:
        item = await _build_assistant_list_item(assistant_manager, info)
        result.append(item)

    return result


@router.get("/{name}/")
async def get_assistant(name: str) -> AssistantDetails:
    """Get detailed information about a specific assistant.

    Args:
        name: Assistant name.

    Returns:
        AssistantDetails with full assistant information.

    Raises:
        404: If assistant not found.
    """
    assistant_manager = _get_assistant_manager()

    try:
        details = await assistant_manager.get_assistant_details(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return AssistantDetails(**details)


@router.get("/{name}/resolved")
async def get_resolved_assistant(name: str) -> ResolvedAssistant:
    """Get the resolved/flattened view of an assistant with source tracking.

    This shows what will actually run when the assistant is used, with tracking
    of which assistant contributed each component (for override visualization).

    Args:
        name: Assistant name.

    Returns:
        ResolvedAssistant with flattened modules and source tracking.

    Raises:
        404: If assistant not found.
    """
    assistant_manager = _get_assistant_manager()

    try:
        resolved = await assistant_manager.get_resolved_assistant(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ResolvedAssistant(**resolved)


@router.get("/{name}/source")
async def get_assistant_source(name: str) -> AssistantSource:
    """Get the raw source content of an assistant file.

    Args:
        name: Assistant name.

    Returns:
        AssistantSource with raw file content.

    Raises:
        404: If assistant not found.
    """
    assistant_manager = _get_assistant_manager()

    try:
        content, path, file_format = await assistant_manager.get_assistant_source(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return AssistantSource(
        name=name,
        content=content,
        path=path,
        format=file_format,
    )


@router.post("/")
async def create_assistant(request: CreateAssistantRequest) -> AssistantListItem:
    """Create a new user assistant.

    Args:
        request: Assistant creation request with name and optional base assistant.

    Returns:
        AssistantListItem for the new assistant.

    Raises:
        400: If assistant name already exists.
    """
    assistant_manager = _get_assistant_manager()

    try:
        info = await assistant_manager.create_assistant(
            name=request.name,
            base_assistant=request.base_assistant,
            description=request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await _build_assistant_list_item(assistant_manager, info)


@router.post("/{name}/copy")
async def copy_assistant(name: str, request: CopyAssistantRequest) -> AssistantListItem:
    """Copy an assistant to user assistants.

    Args:
        name: Source assistant name.
        request: Copy request with new assistant name.

    Returns:
        AssistantListItem for the new assistant.

    Raises:
        404: If source assistant not found.
        400: If new name already exists.
    """
    assistant_manager = _get_assistant_manager()

    try:
        info = await assistant_manager.copy_assistant(name, request.new_name)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return await _build_assistant_list_item(assistant_manager, info)


@router.put("/{name}/")
async def update_assistant(name: str, request: UpdateAssistantRequest) -> AssistantListItem:
    """Update a user assistant's content.

    Args:
        name: Assistant name.
        request: Update request with new content.

    Returns:
        AssistantListItem for the updated assistant.

    Raises:
        404: If assistant not found.
        403: If trying to update a system assistant.
    """
    assistant_manager = _get_assistant_manager()

    info = assistant_manager.get_assistant_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {name}")

    if info.source != "user":
        raise HTTPException(status_code=403, detail=f"Cannot update system assistant: {name}")

    try:
        assistant_manager.update_assistant(name, request.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await _build_assistant_list_item(assistant_manager, info)


@router.post("/{name}/rename")
async def rename_assistant(name: str, request: RenameAssistantRequest) -> AssistantListItem:
    """Rename a user assistant.

    Args:
        name: Current assistant name.
        request: Rename request with new name.

    Returns:
        AssistantListItem for the renamed assistant.

    Raises:
        404: If assistant not found.
        403: If trying to rename a system assistant.
        400: If new name already exists.
    """
    assistant_manager = _get_assistant_manager()

    try:
        info = assistant_manager.rename_assistant(name, request.new_name)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        if "system assistant" in str(e).lower():
            raise HTTPException(status_code=403, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))

    return await _build_assistant_list_item(assistant_manager, info)


@router.delete("/{name}/")
async def delete_assistant(name: str) -> dict[str, str]:
    """Delete an assistant.

    Args:
        name: Assistant name.

    Returns:
        Success message.

    Raises:
        404: If assistant not found.
    """
    assistant_manager = _get_assistant_manager()

    info = assistant_manager.get_assistant_info(name)
    if not info:
        raise HTTPException(status_code=404, detail=f"Assistant not found: {name}")

    try:
        assistant_manager.delete_assistant(name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": f"Assistant deleted: {name}"}
