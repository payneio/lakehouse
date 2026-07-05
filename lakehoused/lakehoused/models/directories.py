"""Models for directory browsing operations."""

from pydantic import BaseModel
from pydantic import Field


class DirectoryListResponse(BaseModel):
    """Response for listing directories.

    Contract:
    - current_path: Relative path to current directory (from data_path)
    - parent_path: Relative path to parent directory, null if at root
    - directories: List of directory names (not full paths)
    """

    current_path: str = Field(..., description="Current directory path relative to data_path")
    parent_path: str | None = Field(None, description="Parent directory path, null if at root")
    directories: list[str] = Field(..., description="List of directory names in current directory")


class DirectoryCreateRequest(BaseModel):
    """Request to create a new directory."""

    relative_path: str = Field(..., description="Path relative to data_path where directory will be created")


class DirectoryCreateResponse(BaseModel):
    """Response after creating a directory."""

    created_path: str = Field(..., description="Relative path to created directory")
    absolute_path: str = Field(..., description="Absolute filesystem path to created directory")


class FileEntry(BaseModel):
    """A file or directory entry for completion."""

    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Relative path from the base directory")
    is_directory: bool = Field(..., description="True if this is a directory")


class FileCompletionResponse(BaseModel):
    """Response for file completion queries.

    Returns files and directories that can be used for @mention completion.
    """

    entries: list[FileEntry] = Field(..., description="List of matching files and directories")
    base_path: str = Field(..., description="Base path the entries are relative to")


class FileContentResponse(BaseModel):
    """Response containing file content for viewing."""

    path: str = Field(..., description="Relative path to the file")
    name: str = Field(..., description="File name")
    content: str = Field(..., description="File content as text")
    size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    is_viewable: bool = Field(..., description="Whether the file can be viewed as text")
