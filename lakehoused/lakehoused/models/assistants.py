"""API models for assistant operations."""

from pydantic import Field

from lakehoused.models.base import CamelCaseModel


class ModuleRef(CamelCaseModel):
    """Module reference in an assistant."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")


class ResolvedModuleRef(CamelCaseModel):
    """Module reference with source tracking for resolved assistants."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")

    # Source tracking
    defined_in: str = Field(description="Which assistant defined this module")
    overridden: bool = Field(default=False, description="Whether this is overridden in the current assistant")
    override_in: str | None = Field(default=None, description="Which assistant overrides this (if overridden)")
    original_config: dict[str, object] | None = Field(
        default=None, description="Original config before override (if overridden)"
    )


class SessionConfigRef(CamelCaseModel):
    """Session configuration reference."""

    orchestrator: ModuleRef | None = Field(default=None, description="Orchestrator module")
    context: ModuleRef | None = Field(default=None, description="Context manager module")


class ResolvedSessionConfig(CamelCaseModel):
    """Session configuration with source tracking."""

    orchestrator: ResolvedModuleRef | None = Field(default=None, description="Orchestrator module with source")
    context: ResolvedModuleRef | None = Field(default=None, description="Context manager module with source")


class AssistantListItem(CamelCaseModel):
    """Assistant list item with summary information."""

    name: str = Field(description="Assistant name")
    version: str = Field(default="1.0.0", description="Assistant version")
    description: str | None = Field(default=None, description="Assistant description")
    source: str = Field(description="Assistant source: 'user' or 'system'")
    path: str = Field(description="Path to assistant file")

    # Quick stats
    provider_count: int = Field(default=0, description="Number of providers")
    tool_count: int = Field(default=0, description="Number of tools")
    hook_count: int = Field(default=0, description="Number of hooks")
    agent_count: int = Field(default=0, description="Number of agents")

    # Composition
    includes: list[str] = Field(default_factory=list, description="Included assistant references")


class AssistantDetails(CamelCaseModel):
    """Full assistant details (raw structure)."""

    name: str = Field(description="Assistant name")
    version: str = Field(default="1.0.0", description="Assistant version")
    description: str | None = Field(default=None, description="Assistant description")
    source: str = Field(description="Assistant source: 'user' or 'system'")
    path: str = Field(description="Path to assistant file")

    # Quick stats
    provider_count: int = Field(default=0, description="Number of providers")
    tool_count: int = Field(default=0, description="Number of tools")
    hook_count: int = Field(default=0, description="Number of hooks")
    agent_count: int = Field(default=0, description="Number of agents")

    # Composition
    includes: list[str] = Field(default_factory=list, description="Included assistant references")

    # Full structure
    session: SessionConfigRef | None = Field(default=None, description="Session configuration")
    providers: list[ModuleRef] = Field(default_factory=list, description="Provider modules")
    tools: list[ModuleRef] = Field(default_factory=list, description="Tool modules")
    hooks: list[ModuleRef] = Field(default_factory=list, description="Hook modules")
    agents: list[ModuleRef] = Field(default_factory=list, description="Agent modules")
    context: dict[str, str] = Field(default_factory=dict, description="Context file mappings")
    instruction: str | None = Field(default=None, description="System instruction (markdown body)")


class IncludesTreeNode(CamelCaseModel):
    """Tree node for assistant includes hierarchy."""

    name: str = Field(description="Assistant name")
    includes: list["IncludesTreeNode"] = Field(
        default_factory=list, description="Child assistants this assistant includes"
    )


class ResolvedAssistant(CamelCaseModel):
    """Flattened assistant with source tracking.

    This is the resolved view showing what will actually run,
    with tracking of which assistant contributed each component.
    """

    name: str = Field(description="Assistant name")
    source: str = Field(description="Assistant source: 'user' or 'system'")
    git_url: str | None = Field(default=None, description="Git URL for system/registry assistants")
    includes_chain: list[str] = Field(
        default_factory=list, description="Full includes chain (e.g., ['foundation/base', 'basic', 'my-assistant'])"
    )
    includes_tree: IncludesTreeNode | None = Field(
        default=None, description="Tree structure showing includes hierarchy"
    )

    # Resolved sections with source tracking
    session: ResolvedSessionConfig | None = Field(default=None, description="Session configuration with source")
    providers: list[ResolvedModuleRef] = Field(default_factory=list, description="Provider modules with source")
    tools: list[ResolvedModuleRef] = Field(default_factory=list, description="Tool modules with source")
    hooks: list[ResolvedModuleRef] = Field(default_factory=list, description="Hook modules with source")
    agents: list[ResolvedModuleRef] = Field(default_factory=list, description="Agent modules with source")

    # Content from final assistant
    instruction: str | None = Field(default=None, description="System instruction")


class AssistantSource(CamelCaseModel):
    """Raw assistant source content."""

    name: str = Field(description="Assistant name")
    content: str = Field(description="Raw assistant file content")
    path: str = Field(description="Path to assistant file")
    format: str = Field(description="File format: 'md', 'yaml', or 'directory'")


class CreateAssistantRequest(CamelCaseModel):
    """Request to create a new assistant."""

    name: str = Field(pattern=r"^[a-z0-9-]+$", description="Assistant name (kebab-case)")
    base_assistant: str | None = Field(default=None, description="Assistant to extend (creates include)")
    description: str | None = Field(default=None, description="Assistant description")


class CopyAssistantRequest(CamelCaseModel):
    """Request to copy an assistant."""

    new_name: str = Field(pattern=r"^[a-z0-9-]+$", description="New assistant name (kebab-case)")


class UpdateAssistantRequest(CamelCaseModel):
    """Request to update an assistant."""

    content: str = Field(description="Raw assistant content (markdown with YAML frontmatter)")


class RenameAssistantRequest(CamelCaseModel):
    """Request to rename an assistant."""

    new_name: str = Field(pattern=r"^[a-z0-9-]+$", description="New assistant name (kebab-case)")
