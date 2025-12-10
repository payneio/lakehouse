"""Directory browsing API endpoints."""

import logging
from functools import lru_cache
from pathlib import Path

from amplifier_library.config.loader import load_config
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from amplifierd.models.directories import DirectoryCreateRequest
from amplifierd.models.directories import DirectoryCreateResponse
from amplifierd.models.directories import DirectoryListResponse
from amplifierd.services.amplified_directory_service import AmplifiedDirectoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/directories", tags=["directories"])


@lru_cache(maxsize=1)
def get_service() -> AmplifiedDirectoryService:
    """Get amplified directory service singleton instance."""
    config = load_config()
    data_path = Path(config.data_path)
    return AmplifiedDirectoryService(data_path)


@router.get("/list", response_model=DirectoryListResponse)
async def list_directories(
    path: str = Query(default="", description="Relative path to list, defaults to root"),
    service: AmplifiedDirectoryService = Depends(get_service),
) -> DirectoryListResponse:
    """List immediate child directories at specified path.

    Returns only directories (not files), excludes hidden directories except shows empty result.

    Args:
        path: Relative path from data_path root (default: "" for root)
        service: Injected service instance

    Returns:
        DirectoryListResponse with current path, parent path, and directory names

    Raises:
        400: Invalid path (absolute, contains '..', or escapes root)
        404: Path doesn't exist
        403: Path is not a directory
    """
    try:
        # Validate and resolve the path
        dir_path = service._validate_and_resolve_path(path)

        # Check if path exists and is a directory
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

        if not dir_path.is_dir():
            raise HTTPException(status_code=403, detail=f"Path is not a directory: {path}")

        # List only directories (not files, not hidden except if empty)
        directories = [
            item.name for item in sorted(dir_path.iterdir()) if item.is_dir() and not item.name.startswith(".")
        ]

        # Calculate parent path
        parent_path: str | None = None
        if path and path != ".":
            parent = Path(path).parent
            parent_path = str(parent) if str(parent) != "." else ""

        return DirectoryListResponse(
            current_path=path,
            parent_path=parent_path,
            directories=directories,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid path for listing: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to list directories at {path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/create", response_model=DirectoryCreateResponse, status_code=201)
async def create_directory(
    request: DirectoryCreateRequest,
    service: AmplifiedDirectoryService = Depends(get_service),
) -> DirectoryCreateResponse:
    """Create a new directory at specified path.

    Creates parent directories if needed (mkdir -p behavior).

    Args:
        request: Creation request with relative_path
        service: Injected service instance

    Returns:
        DirectoryCreateResponse with created paths

    Raises:
        400: Invalid path (absolute, contains '..', or escapes root)
        500: Filesystem error during creation
    """
    try:
        # Validate and resolve the path
        dir_path = service._validate_and_resolve_path(request.relative_path)

        # Create directory (parents=True for mkdir -p behavior)
        dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Created directory: {request.relative_path}")

        return DirectoryCreateResponse(
            created_path=request.relative_path,
            absolute_path=str(dir_path),
        )

    except ValueError as e:
        logger.warning(f"Invalid path for creation: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to create directory {request.relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
