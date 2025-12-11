"""API models for module operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ModuleInfo(CamelCaseModel):
    """Basic module information."""

    id: str = Field(description="Module identifier")
    type: str = Field(description="Module type (provider, hook, tool, orchestrator)")
    name: str = Field(description="Module name")
    location: str = Field(description="Module file path")
    source: str | None = Field(default=None, description="Module source (local, registry, git)")


class ModuleDetails(CamelCaseModel):
    """Detailed module information."""

    id: str = Field(description="Module identifier")
    type: str = Field(description="Module type (provider, hook, tool, orchestrator)")
    name: str = Field(description="Module name")
    location: str = Field(description="Module file path")
    source: str | None = Field(default=None, description="Module source (local, registry, git)")
    description: str | None = Field(default=None, description="Module description")
    config_schema: dict[str, object] | None = Field(default=None, description="Module configuration schema")
