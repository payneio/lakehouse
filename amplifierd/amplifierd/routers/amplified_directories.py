"""Amplified directories API endpoints."""

import logging
from functools import lru_cache
from pathlib import Path

from amplifier_library.config.loader import load_config
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from amplifierd.models.amplified_directories import AgentsContentResponse
from amplifierd.models.amplified_directories import AgentsContentUpdate
from amplifierd.models.amplified_directories import AmplifiedDirectory
from amplifierd.models.amplified_directories import AmplifiedDirectoryCreate
from amplifierd.models.amplified_directories import AmplifiedDirectoryList
from amplifierd.models.amplified_directories import AmplifiedDirectoryUpdate
from amplifierd.services.amplified_directory_service import AmplifiedDirectoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amplified-directories", tags=["amplified-directories"])


@lru_cache(maxsize=1)
def get_service() -> AmplifiedDirectoryService:
    """Get amplified directory service singleton instance."""
    config = load_config()
    data_path = Path(config.data_path)
    return AmplifiedDirectoryService(data_path)


@router.post("/", response_model=AmplifiedDirectory, status_code=201)
async def create_amplified_directory(
    create_req: AmplifiedDirectoryCreate,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AmplifiedDirectory:
    """Create/register a new amplified directory.

    Creates directory structure and .amplified marker if requested.
    Resolves default_profile using inheritance if not provided.

    Args:
        create_req: Creation request with path, optional profile, metadata
        service: Injected service instance

    Returns:
        Created AmplifiedDirectory with resolved profile

    Raises:
        400: Invalid path (absolute, contains '..', escapes root)
        400: Directory already amplified
        500: Filesystem error
    """
    try:
        return service.create(create_req)
    except ValueError as e:
        logger.warning(f"Invalid create request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to create amplified directory: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/root", response_model=AmplifiedDirectory)
async def get_root_directory(
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AmplifiedDirectory:
    """Get root amplified directory (special endpoint for path '.').

    FastAPI routes /amplified-directories/. to the list endpoint,
    so we provide /amplified-directories/root as an explicit route.

    Returns:
        Root amplified directory with metadata and agents_content

    Raises:
        404: Root directory not amplified
    """
    try:
        directory = service.get(".")

        if not directory:
            raise HTTPException(status_code=404, detail="Root directory not amplified")

        return directory
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get root directory: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/", response_model=AmplifiedDirectoryList)
async def list_amplified_directories(
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AmplifiedDirectoryList:
    """List all amplified directories within AMPLIFIERD_DATA_PATH.

    Discovers directories by walking filesystem to find .amplified markers.

    Returns:
        List of all amplified directories with metadata
    """
    try:
        directories = service.list_all()
        return AmplifiedDirectoryList(
            directories=directories,
            total=len(directories),
        )
    except Exception as e:
        logger.error(f"Failed to list amplified directories: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{relative_path:path}", response_model=AmplifiedDirectory)
async def get_amplified_directory(
    relative_path: str,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AmplifiedDirectory:
    """Get specific amplified directory by relative path.

    Args:
        relative_path: Path relative to AMPLIFIERD_DATA_PATH
        service: Injected service instance

    Returns:
        AmplifiedDirectory with metadata

    Raises:
        404: Directory not found or not amplified
    """
    try:
        directory = service.get(relative_path)

        if not directory:
            raise HTTPException(status_code=404, detail=f"Amplified directory not found: {relative_path}")

        return directory

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get amplified directory {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.patch("/{relative_path:path}", response_model=AmplifiedDirectory)
async def update_amplified_directory(
    relative_path: str,
    update_req: AmplifiedDirectoryUpdate,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AmplifiedDirectory:
    """Update amplified directory metadata.

    Merges provided metadata with existing metadata.

    Args:
        relative_path: Path relative to AMPLIFIERD_DATA_PATH
        update_req: Update request with metadata changes
        service: Injected service instance

    Returns:
        Updated AmplifiedDirectory

    Raises:
        404: Directory not found or not amplified
        500: Update failed
    """
    try:
        directory = service.update(relative_path, update_req)

        if not directory:
            raise HTTPException(status_code=404, detail=f"Amplified directory not found: {relative_path}")

        return directory

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update amplified directory {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.put("/root/agents", response_model=AgentsContentResponse)
async def update_root_agents_content(
    update_req: AgentsContentUpdate,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AgentsContentResponse:
    """Update AGENTS.md file for root amplified directory (special endpoint for path '.').

    FastAPI has issues routing '.' in paths, so we provide /root/agents as an explicit route.

    Args:
        update_req: New content for AGENTS.md
        service: Injected service instance

    Returns:
        Success status and message

    Raises:
        404: Root directory not amplified
        400: Invalid content (empty)
        500: File write failed
    """
    try:
        # Basic validation
        if not update_req.content.strip():
            raise HTTPException(status_code=400, detail="AGENTS.md content cannot be empty")

        # Update agents file for root directory
        success = service.update_agents_content(".", update_req.content)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Root directory not amplified",
            )

        return AgentsContentResponse(
            success=True,
            message="AGENTS.md updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update AGENTS.md for root directory: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update AGENTS.md: {str(e)}",
        ) from e


@router.put("/{relative_path:path}/agents", response_model=AgentsContentResponse)
async def update_agents_content(
    relative_path: str,
    update_req: AgentsContentUpdate,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> AgentsContentResponse:
    """Update AGENTS.md file for an amplified directory.

    Args:
        relative_path: Path relative to AMPLIFIERD_DATA_PATH
        update_req: New content for AGENTS.md
        service: Injected service instance

    Returns:
        Success status and message

    Raises:
        404: Directory not found or not amplified
        400: Invalid content (empty)
        500: File write failed
    """
    try:
        # Basic validation
        if not update_req.content.strip():
            raise HTTPException(status_code=400, detail="AGENTS.md content cannot be empty")

        # Update agents file
        success = service.update_agents_content(relative_path, update_req.content)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Amplified directory not found: {relative_path}",
            )

        return AgentsContentResponse(
            success=True,
            message="AGENTS.md updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update AGENTS.md for {relative_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update AGENTS.md: {str(e)}",
        ) from e


@router.delete("/{relative_path:path}", status_code=204)
async def delete_amplified_directory(
    relative_path: str,
    remove_marker: bool = False,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> None:
    """Unregister/delete amplified directory.

    Args:
        relative_path: Path relative to AMPLIFIERD_DATA_PATH
        remove_marker: If True, also delete .amplified directory from filesystem
        service: Injected service instance

    Raises:
        404: Directory not found or not amplified
        409: Cannot delete - directory has active sessions
        500: Deletion failed

    Note: Deletion protection (409) will be implemented when session
    integration is complete. For now, deletion always proceeds if directory exists.
    """
    try:
        # Session deletion protection will be implemented when session integration is complete
        # The service will check for active sessions and raise 409 if any exist

        success = service.delete(relative_path, remove_marker=remove_marker)

        if not success:
            raise HTTPException(status_code=404, detail=f"Amplified directory not found: {relative_path}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete amplified directory {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
