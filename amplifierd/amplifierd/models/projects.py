from datetime import datetime
from pathlib import Path

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


class Project(BaseModel):
    """
    Represents a directory within AMPLIFIERD_DATA_PATH containing .amplified marker.

    Contract:
    - relative_path: Path relative to AMPLIFIERD_DATA_PATH
    - default_bundle: Default bundle for new sessions (extracted from metadata)
    - metadata: User-defined metadata
    - created_at: Directory registration timestamp
    - last_used_at: Last session creation timestamp
    - path: Absolute path to directory
    - is_project: Always True for this model

    Metadata schema:
    {
        "default_bundle": "foundation/foundation",  # Required: bundle for new sessions
        "name": "Project Name",                      # Optional: human-readable name
        "description": "...",                        # Optional: description
        ... other user-defined fields
    }
    """

    relative_path: str = Field(..., description="Path relative to AMPLIFIERD_DATA_PATH")
    default_bundle: str | None = Field(None, description="Default bundle for new sessions")
    metadata: dict = Field(..., description="User metadata")
    agents_content: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: datetime | None = None
    path: str = Field("", description="Absolute path to directory")
    is_project: bool = Field(True, description="Always true for projects")

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


class ProjectCreate(BaseModel):
    """Request to create/register a new project"""

    relative_path: str
    default_bundle: str | None = None
    metadata: dict | None = None
    create_marker: bool = Field(default=True, description="Create .amplified if missing")


class ProjectUpdate(BaseModel):
    """Request to update project metadata"""

    default_bundle: str | None = None
    metadata: dict | None = None


class ProjectList(BaseModel):
    """Response containing list of projects"""

    projects: list[Project]
    total: int


class AgentsContentUpdate(BaseModel):
    """Request to update AGENTS.md content"""

    content: str = Field(..., description="New content for AGENTS.md file")


class AgentsContentResponse(BaseModel):
    """Response from updating AGENTS.md"""

    success: bool = Field(..., description="Whether update succeeded")
    message: str = Field(..., description="Success or error message")
