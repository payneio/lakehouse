"""API models for profile operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ProfileInfo(CamelCaseModel):
    """Basic profile information."""

    name: str = Field(description="Profile name")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")
    collection_id: str | None = Field(default=None, description="Collection this profile belongs to")
    schema_version: int | None = Field(default=None, description="Profile schema version")


class ModuleConfig(CamelCaseModel):
    """Module configuration in a profile."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")


class SessionConfig(CamelCaseModel):
    """Session configuration for profile."""

    orchestrator: ModuleConfig = Field(description="Orchestrator module configuration")
    context_manager: ModuleConfig | None = Field(default=None, description="Context manager module configuration")


class ProfileDetails(CamelCaseModel):
    """Detailed profile information."""

    name: str = Field(description="Profile name")
    schema_version: int = Field(default=1, description="Profile schema version (1 or 2)")
    version: str = Field(description="Profile version")
    description: str = Field(description="Profile description")
    collection_id: str | None = Field(default=None, description="Collection this profile belongs to")
    source: str = Field(description="Profile source (user, project, collection)")
    is_active: bool = Field(description="Whether this profile is currently active")
    inheritance_chain: list[str] = Field(default_factory=list, description="Profile inheritance chain (schema v1 only)")
    providers: list[ModuleConfig] = Field(description="Provider modules")
    tools: list[ModuleConfig] = Field(description="Tool modules")
    hooks: list[ModuleConfig] = Field(description="Hook modules")
    session: SessionConfig | None = Field(default=None, description="Session configuration (schema v2)")
    agents: list[str] = Field(default_factory=list, description="Agent file references")
    context: list[str] = Field(default_factory=list, description="Context directory references")
