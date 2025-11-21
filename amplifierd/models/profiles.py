"""API models for profile operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ProfileInfo(CamelCaseModel):
    """Basic profile information."""

    name: str = Field(description="Profile name")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")


class ModuleConfig(CamelCaseModel):
    """Module configuration in a profile."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")


class ProfileDetails(CamelCaseModel):
    """Detailed profile information."""

    name: str = Field(description="Profile name")
    version: str = Field(description="Profile version")
    description: str = Field(description="Profile description")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")
    inheritance_chain: list[str] = Field(description="Profile inheritance chain")
    providers: list[ModuleConfig] = Field(description="Provider modules")
    tools: list[ModuleConfig] = Field(description="Tool modules")
    hooks: list[ModuleConfig] = Field(description="Hook modules")
