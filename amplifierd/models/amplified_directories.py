from datetime import datetime
from pathlib import Path

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class AmplifiedDirectory(BaseModel):
    """
    Represents a directory within AMPLIFIERD_DATA_PATH containing .amplified marker.

    Contract:
    - relative_path: Path relative to AMPLIFIERD_DATA_PATH
    - default_profile: Default profile for new sessions (extracted from metadata)
    - metadata: User-defined metadata
    - created_at: Directory registration timestamp
    - last_used_at: Last session creation timestamp
    - path: Absolute path to directory
    - is_amplified: Always True for this model

    Metadata schema:
    {
        "default_profile": "foundation/foundation",  # Required: profile for new sessions
        "name": "Project Name",                      # Optional: human-readable name
        "description": "...",                        # Optional: description
        ... other user-defined fields
    }
    """

    relative_path: str = Field(..., description="Path relative to AMPLIFIERD_DATA_PATH")
    default_profile: str | None = Field(None, description="Default profile for new sessions")
    metadata: dict = Field(..., description="User metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = None
    path: str = Field("", description="Absolute path to directory")
    is_amplified: bool = Field(True, description="Always true for amplified directories")

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, v: str) -> str:
        """Ensure path is relative and doesn't escape root"""
        path = Path(v)
        if path.is_absolute():
            raise ValueError("relative_path must be relative")
        if any(part == ".." for part in path.parts):
            raise ValueError("relative_path cannot contain '..'")
        return v


class AmplifiedDirectoryCreate(BaseModel):
    """Request to create/register a new amplified directory"""

    relative_path: str
    default_profile: str | None = None
    metadata: dict | None = None
    create_marker: bool = Field(default=True, description="Create .amplified if missing")


class AmplifiedDirectoryUpdate(BaseModel):
    """Request to update amplified directory metadata"""

    default_profile: str | None = None
    metadata: dict | None = None


class AmplifiedDirectoryList(BaseModel):
    """Response containing list of amplified directories"""

    directories: list[AmplifiedDirectory]
    total: int
