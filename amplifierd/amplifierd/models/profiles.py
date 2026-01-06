"""API models for profile operations."""

from typing import Any

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class CreateProfileRequest(CamelCaseModel):
    """Request body for creating a new bundle profile.

    Fields match amplifier-foundation Bundle dataclass structure.
    """

    name: str = Field(description="Bundle name")
    version: str = Field(default="1.0.0", description="Bundle version")
    description: str = Field(default="", description="Bundle description")
    includes: list[str] = Field(default_factory=list, description="List of bundle URIs to include")

    # Mount plan sections
    session: dict[str, Any] = Field(default_factory=dict, description="Session config (orchestrator, context)")
    providers: list[dict[str, Any]] = Field(default_factory=list, description="Provider module configs")
    tools: list[dict[str, Any]] = Field(default_factory=list, description="Tool module configs")
    hooks: list[dict[str, Any]] = Field(default_factory=list, description="Hook module configs")

    # Resources
    agents: dict[str, dict[str, Any]] = Field(default_factory=dict, description="Agent definitions")
    context: dict[str, str] = Field(default_factory=dict, description="Context file paths")
    instruction: str | None = Field(default=None, description="System instruction markdown")


class UpdateProfileRequest(CamelCaseModel):
    """Request body for updating a bundle profile.

    All fields optional - only provided fields will be updated.
    """

    version: str | None = Field(default=None, description="Bundle version")
    description: str | None = Field(default=None, description="Bundle description")
    includes: list[str] | None = Field(default=None, description="List of bundle URIs to include")

    # Mount plan sections
    session: dict[str, Any] | None = Field(default=None, description="Session config (orchestrator, context)")
    providers: list[dict[str, Any]] | None = Field(default=None, description="Provider module configs")
    tools: list[dict[str, Any]] | None = Field(default=None, description="Tool module configs")
    hooks: list[dict[str, Any]] | None = Field(default=None, description="Hook module configs")

    # Resources
    agents: dict[str, dict[str, Any]] | None = Field(default=None, description="Agent definitions")
    context: dict[str, str] | None = Field(default=None, description="Context file paths")
    instruction: str | None = Field(default=None, description="System instruction markdown")


class ProfileInfo(CamelCaseModel):
    """Basic profile information."""

    name: str = Field(description="Profile name")
    source: str = Field(description="Profile source path")
    source_type: str = Field(default="local", description="Profile source type (local or registry)")
    registry_id: str | None = Field(default=None, description="Registry ID if from registry")
    source_uri: str | None = Field(default=None, description="Original source URI if from registry")
    is_active: bool = Field(description="Whether this profile is currently active")
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
    """Detailed profile information (v3)."""

    name: str = Field(description="Profile name")
    schema_version: int = Field(default=3, description="Profile schema version (3 only)")
    version: str = Field(description="Profile version")
    description: str = Field(description="Profile description")
    source: str = Field(description="Profile source path")
    source_type: str = Field(default="local", description="Profile source type (local or registry)")
    registry_id: str | None = Field(default=None, description="Registry ID if from registry")
    source_uri: str | None = Field(default=None, description="Original source URI if from registry")
    is_active: bool = Field(description="Whether this profile is currently active")
    behaviors: list["BehaviorRef"] = Field(default_factory=list, description="Behavior references")
    providers: list[ModuleConfig] = Field(default_factory=list, description="Provider modules")
    tools: list[ModuleConfig] = Field(default_factory=list, description="Tool modules")
    hooks: list[ModuleConfig] = Field(default_factory=list, description="Hook modules")
    session: SessionConfig | None = Field(default=None, description="Session configuration")
    agents: dict[str, str] = Field(default_factory=dict, description="Agent content (name -> markdown)")
    contexts: dict[str, str] = Field(default_factory=dict, description="Context content (name -> ref)")
    instruction: str | None = Field(default=None, description="Profile system instruction")


class ComponentRef(CamelCaseModel):
    """Component reference with inline source (v3)."""

    id: str = Field(description="Component identifier")
    type: str = Field(description="Component type (orchestrator, tool, hook, agent, context, provider)")
    source: str | None = Field(default=None, description="Component source URI (amp://, git+, file://)")
    config: dict[str, object] | None = Field(default=None, description="Component-specific configuration")


class BehaviorRef(CamelCaseModel):
    """Behavior reference (v3)."""

    id: str = Field(description="Behavior identifier")
    source: str = Field(description="Behavior source URI (amp://, git+, file://)")
    config: dict[str, object] | None = Field(default=None, description="Behavior-specific configuration")
