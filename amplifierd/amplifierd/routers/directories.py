"""Directory browsing API endpoints."""

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query

from amplifier_library.config.loader import load_config
from amplifierd.models.directories import DirectoryCreateRequest
from amplifierd.models.directories import DirectoryCreateResponse
from amplifierd.models.directories import DirectoryListResponse
from amplifierd.models.directories import FileCompletionResponse
from amplifierd.models.directories import FileEntry
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


@router.get("/files", response_model=FileCompletionResponse)
async def list_files_for_completion(
    path: str = Query(default="", description="Base path to list files from"),
    prefix: str = Query(default="", description="Optional prefix to filter files/dirs"),
    max_results: int = Query(default=50, ge=1, le=200, description="Maximum results to return"),
    service: AmplifiedDirectoryService = Depends(get_service),
) -> FileCompletionResponse:
    """List files and directories for @mention completion.

    Returns both files and directories (excluding hidden), useful for autocomplete.
    Results are sorted with directories first, then files, both alphabetically.

    Args:
        path: Base path relative to data_path root
        prefix: Filter results to those starting with this prefix
        max_results: Maximum number of entries to return (default 50, max 200)
        service: Injected service instance

    Returns:
        FileCompletionResponse with matching files and directories
    """
    try:
        # Validate and resolve the base path
        base_path = service._validate_and_resolve_path(path) if path else service.root

        if not base_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

        if not base_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")

        entries: list[FileEntry] = []

        # Collect directories and files, excluding hidden
        for item in sorted(base_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name.startswith("."):
                continue

            # Filter by prefix if provided
            if prefix and not item.name.lower().startswith(prefix.lower()):
                continue

            # Calculate relative path from the base
            rel_path = item.name

            entries.append(
                FileEntry(
                    name=item.name,
                    path=rel_path,
                    is_directory=item.is_dir(),
                )
            )

            if len(entries) >= max_results:
                break

        return FileCompletionResponse(
            entries=entries,
            base_path=path,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid path for file listing: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to list files at {path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# Viewable text file extensions
VIEWABLE_TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".scss",
    ".xml",
    ".csv",
    ".sh",
    ".bash",
    ".zsh",
    ".conf",
    ".ini",
    ".cfg",
    ".env",
    ".gitignore",
    ".dockerfile",
    ".makefile",
    ".rst",
    ".tex",
    ".sql",
    ".r",
    ".rb",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".java",
    ".kt",
    ".swift",
    ".lua",
    ".pl",
    ".php",
    ".vue",
    ".svelte",
}

# Viewable image extensions
VIEWABLE_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".bmp",
    ".ico",
}

# Max file size for viewing text (1MB)
MAX_VIEWABLE_TEXT_SIZE = 1024 * 1024

# Max file size for viewing images (10MB)
MAX_VIEWABLE_IMAGE_SIZE = 10 * 1024 * 1024


def is_viewable_text_file(file_path: Path) -> bool:
    """Check if a file can be viewed as text."""
    suffix = file_path.suffix.lower()
    if suffix in VIEWABLE_TEXT_EXTENSIONS:
        return True
    return file_path.name.lower() in {"readme", "license", "changelog", "makefile", "dockerfile", "vagrantfile"}


def is_viewable_image_file(file_path: Path) -> bool:
    """Check if a file is a viewable image."""
    return file_path.suffix.lower() in VIEWABLE_IMAGE_EXTENSIONS


def get_mime_type(file_path: Path) -> str:
    """Get MIME type for a file."""
    import mimetypes

    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


@router.get("/file/content")
async def get_file_content(
    path: str = Query(..., description="Relative path to the file"),
    service: AmplifiedDirectoryService = Depends(get_service),
) -> dict:
    """Get file content for viewing.

    Returns file content as text for viewable files. For non-viewable files,
    returns metadata indicating the file cannot be viewed.

    Args:
        path: Relative path to the file from data_path root
        service: Injected service instance

    Returns:
        File content and metadata, or indication that file is not viewable
    """
    try:
        file_path = service._validate_and_resolve_path(path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        if file_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is a directory: {path}")

        file_size = file_path.stat().st_size
        mime_type = get_mime_type(file_path)

        # Check if it's a viewable image
        is_image = is_viewable_image_file(file_path) and file_size <= MAX_VIEWABLE_IMAGE_SIZE
        if is_image:
            # Images are viewable but we don't return content - frontend uses download URL
            return {
                "path": path,
                "name": file_path.name,
                "content": "",
                "size": file_size,
                "mime_type": mime_type,
                "is_viewable": True,
                "is_image": True,
            }

        # Check if it's a viewable text file
        is_text = is_viewable_text_file(file_path) and file_size <= MAX_VIEWABLE_TEXT_SIZE
        if not is_text:
            return {
                "path": path,
                "name": file_path.name,
                "content": "",
                "size": file_size,
                "mime_type": mime_type,
                "is_viewable": False,
                "is_image": False,
            }

        # Read text file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with latin-1 as fallback
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return {
                    "path": path,
                    "name": file_path.name,
                    "content": "",
                    "size": file_size,
                    "mime_type": mime_type,
                    "is_viewable": False,
                    "is_image": False,
                }

        return {
            "path": path,
            "name": file_path.name,
            "content": content,
            "size": file_size,
            "mime_type": mime_type,
            "is_viewable": True,
            "is_image": False,
        }

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid path for file content: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get file content for {path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/file/download")
async def download_file(
    path: str = Query(..., description="Relative path to the file"),
    service: AmplifiedDirectoryService = Depends(get_service),
):
    """Download a file.

    Returns the file as a download response with appropriate headers.

    Args:
        path: Relative path to the file from data_path root
        service: Injected service instance

    Returns:
        FileResponse for downloading
    """
    from fastapi.responses import FileResponse

    try:
        file_path = service._validate_and_resolve_path(path)

        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        if file_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is a directory: {path}")

        mime_type = get_mime_type(file_path)

        return FileResponse(
            path=file_path,
            filename=file_path.name,
            media_type=mime_type,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid path for file download: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to download file {path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
