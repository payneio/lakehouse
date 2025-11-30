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
