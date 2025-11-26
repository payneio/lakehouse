"""API models for collection operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ProfileManifest(CamelCaseModel):
    """Reference to a profile in a collection."""

    name: str = Field(description="Profile name")
    version: str = Field(description="Profile version")
    path: str = Field(description="Relative path in collection")
    installed_at: str | None = Field(default=None, description="ISO timestamp when profile was fetched/compiled")


class CollectionInfo(CamelCaseModel):
    """Collection information - a set of profile manifests."""

    identifier: str = Field(description="Collection identifier")
    source: str = Field(description="Collection source reference")
    profiles: list[ProfileManifest] = Field(default_factory=list, description="Profile manifests in collection")
