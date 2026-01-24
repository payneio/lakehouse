"""File browsing API endpoints.

Provides filesystem browsing functionality for the webapp, including
directory listing, file completion for @mentions, and file content viewing.
"""

import logging
import mimetypes
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import FileResponse
from lakehouse_library.config.loader import load_config

from lakehoused.models.files import DirectoryCreateRequest
from lakehoused.models.files import DirectoryCreateResponse
from lakehoused.models.files import DirectoryListResponse
from lakehoused.models.files import FileCompletionResponse
from lakehoused.models.files import FileContentResponse
from lakehoused.models.files import FileEntry

logger = logging.getLogger(__name__)

# File extension sets for viewability detection
VIEWABLE_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".xml",
    ".svg",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ps1",
    ".bat",
    ".cmd",
    ".sql",
    ".graphql",
    ".gql",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".hh",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".r",
    ".R",
    ".pl",
    ".pm",
    ".lua",
    ".vim",
    ".el",
    ".clj",
    ".cljs",
    ".edn",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",
    ".hs",
    ".lhs",
    ".ml",
    ".mli",
    ".fs",
    ".fsi",
    ".fsx",
    ".fsscript",
    ".dockerfile",
    ".env",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".prettierrc",
    ".eslintrc",
    ".babelrc",
    ".npmrc",
    ".yarnrc",
    ".nvmrc",
    ".dockerignore",
    ".htaccess",
    ".log",
    ".csv",
    ".tsv",
    ".rst",
    ".tex",
    ".bib",
}

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

# Size limits for viewable files
MAX_VIEWABLE_TEXT_SIZE = 1024 * 1024  # 1MB
MAX_VIEWABLE_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

router = APIRouter(prefix="/api/v1/directories", tags=["files"])


class FileService:
    """Service for file browsing operations."""

    def __init__(self, data_path: Path) -> None:
        """Initialize with root data directory."""
        self.root = Path(data_path).resolve()

    def validate_and_resolve_path(self, relative_path: str) -> Path:
        """Validate and resolve path (security-critical).

        Args:
            relative_path: Path relative to root

        Returns:
            Resolved absolute Path within root

        Raises:
            ValueError: If path is invalid or escapes root
        """
        path = Path(relative_path) if relative_path else Path(".")

        # Reject absolute paths
        if path.is_absolute():
            raise ValueError(f"Path must be relative: {relative_path}")

        # Reject paths containing '..'
        if any(part == ".." for part in path.parts):
            raise ValueError(f"Path cannot contain '..': {relative_path}")

        # Resolve symlinks and verify containment
        full_path = (self.root / path).resolve()

        # Verify path is within root
        try:
            full_path.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Path escapes root: {relative_path}")

        return full_path


@lru_cache(maxsize=1)
def get_service() -> FileService:
    """Get file service singleton instance."""
    config = load_config()
    data_path = Path(config.data_path)
    return FileService(data_path)


def is_viewable_text_file(file_path: Path) -> bool:
    """Check if a file is a viewable text file."""
    # Check extension
    if file_path.suffix.lower() in VIEWABLE_TEXT_EXTENSIONS:
        return True
    # Check for common filenames without extensions
    return file_path.name.lower() in {"dockerfile", "makefile", "readme", "license", "changelog"}


def is_viewable_image_file(file_path: Path) -> bool:
    """Check if a file is a viewable image."""
    return file_path.suffix.lower() in VIEWABLE_IMAGE_EXTENSIONS


def get_mime_type(file_path: Path) -> str:
    """Get MIME type for a file."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


@router.get("/list", response_model=DirectoryListResponse)
async def list_directories(
    path: str = Query(default="", description="Relative path to list, defaults to root"),
    service: FileService = Depends(get_service),
) -> DirectoryListResponse:
    """List immediate child directories at specified path.

    Returns only directories (not files), excludes hidden directories.

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
        dir_path = service.validate_and_resolve_path(path)

        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {path}")

        if not dir_path.is_dir():
            raise HTTPException(status_code=403, detail=f"Path is not a directory: {path}")

        # List only directories (not files, not hidden)
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
    service: FileService = Depends(get_service),
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
        dir_path = service.validate_and_resolve_path(request.relative_path)

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
    service: FileService = Depends(get_service),
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
        base_path = service.validate_and_resolve_path(path) if path else service.root

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


@router.get("/file/content", response_model=FileContentResponse)
async def get_file_content(
    path: str = Query(..., description="Relative path to the file"),
    service: FileService = Depends(get_service),
) -> FileContentResponse:
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
        file_path = service.validate_and_resolve_path(path)

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
            return FileContentResponse(
                path=path,
                name=file_path.name,
                content="",
                size=file_size,
                mime_type=mime_type,
                is_viewable=True,
                is_image=True,
            )

        # Check if it's a viewable text file
        is_text = is_viewable_text_file(file_path) and file_size <= MAX_VIEWABLE_TEXT_SIZE
        if not is_text:
            return FileContentResponse(
                path=path,
                name=file_path.name,
                content="",
                size=file_size,
                mime_type=mime_type,
                is_viewable=False,
                is_image=False,
            )

        # Read text file content
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with latin-1 as fallback
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return FileContentResponse(
                    path=path,
                    name=file_path.name,
                    content="",
                    size=file_size,
                    mime_type=mime_type,
                    is_viewable=False,
                    is_image=False,
                )

        return FileContentResponse(
            path=path,
            name=file_path.name,
            content=content,
            size=file_size,
            mime_type=mime_type,
            is_viewable=True,
            is_image=False,
        )

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
    service: FileService = Depends(get_service),
) -> FileResponse:
    """Download a file.

    Returns the file as a download response with appropriate headers.

    Args:
        path: Relative path to the file from data_path root
        service: Injected service instance

    Returns:
        FileResponse for downloading
    """
    try:
        file_path = service.validate_and_resolve_path(path)

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
