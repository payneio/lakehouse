"""API models for profile operations."""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class CreateProfileRequest(CamelCaseModel):
    """Request body for creating a new profile."""

    name: str = Field(pattern=r"^[a-z0-9-]+$", description="Profile name (kebab-case)")
    version: str = Field(default="1.0.0", description="Profile version")
    description: str = Field(description="Profile description")
    providers: list["ModuleConfig"] = Field(default_factory=list, description="Provider modules")
    tools: list["ModuleConfig"] = Field(default_factory=list, description="Tool modules")
    hooks: list["ModuleConfig"] = Field(default_factory=list, description="Hook modules")
    orchestrator: "ModuleConfig | None" = Field(default=None, description="Orchestrator module")
    context: "ModuleConfig | None" = Field(default=None, description="Context manager module")


class UpdateProfileRequest(CamelCaseModel):
    """Request body for updating a profile. All fields optional."""

    version: str | None = Field(default=None, description="Profile version")
    description: str | None = Field(default=None, description="Profile description")
    providers: list["ModuleConfig"] | None = Field(default=None, description="Provider modules")
    tools: list["ModuleConfig"] | None = Field(default=None, description="Tool modules")
    hooks: list["ModuleConfig"] | None = Field(default=None, description="Hook modules")
    orchestrator: "ModuleConfig | None" = Field(default=None, description="Orchestrator module")
    context: "ModuleConfig | None" = Field(default=None, description="Context manager module")
    agents: dict[str, str] | None = Field(default=None, description="Agent file references (name -> ref)")
    contexts: dict[str, str] | None = Field(default=None, description="Context directory references (name -> ref)")
    instruction: str | None = Field(default=None, description="Profile system instruction (markdown body)")


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
    context: dict[str, str] = Field(default_factory=dict, description="Context directory references (name -> ref)")
    instruction: str | None = Field(default=None, description="Profile system instruction from markdown body")
