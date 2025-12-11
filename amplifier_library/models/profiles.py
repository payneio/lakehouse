"""Profile-related models for amplifier_library."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileMetadata(BaseModel):
    """Metadata tracking profile provenance and state."""

    name: str = Field(description="Profile name")
    source_type: Literal["local", "registry"] = Field(description="Where the profile came from")
    registry_ref: str | None = Field(
        default=None, description="Registry reference if from registry (e.g., 'amp://microsoft/profiles/software-developer.yaml')"
    )
    editable: bool = Field(default=True, description="Whether this profile can be edited")
    last_compiled: datetime | None = Field(default=None, description="When the profile was last compiled to mount_plan.json")
    source_hash: str | None = Field(default=None, description="Hash of profile.yaml for change detection")
    created_from: str | None = Field(default=None, description="Name of profile this was copied from")
