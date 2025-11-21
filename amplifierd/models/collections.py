"""API models for collection operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class CollectionInfo(CamelCaseModel):
    """Basic collection information."""

    identifier: str = Field(description="Collection identifier")
    source: str = Field(description="Collection source path")
    type: str = Field(description="Collection type (git, local)")


class CollectionModules(CamelCaseModel):
    """Module listings in a collection."""

    providers: list[str] = Field(default_factory=list, description="Provider module paths")
    tools: list[str] = Field(default_factory=list, description="Tool module paths")
    hooks: list[str] = Field(default_factory=list, description="Hook module paths")
    orchestrators: list[str] = Field(default_factory=list, description="Orchestrator module paths")


class CollectionDetails(CamelCaseModel):
    """Detailed collection information."""

    identifier: str = Field(description="Collection identifier")
    source: str = Field(description="Collection source path")
    type: str = Field(description="Collection type (git, local)")
    profiles: list[str] = Field(description="Profile paths in collection")
    agents: list[str] = Field(description="Agent paths in collection")
    modules: CollectionModules = Field(description="Module paths in collection")
