"""API models for bundle operations."""

from pydantic import Field

from lakehoused.models.base import CamelCaseModel


class ModuleRef(CamelCaseModel):
    """Module reference in a bundle."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")


class ResolvedModuleRef(CamelCaseModel):
    """Module reference with source tracking for resolved bundles."""

    module: str = Field(description="Module identifier")
    source: str | None = Field(default=None, description="Module source URL or path")
    config: dict[str, object] | None = Field(default=None, description="Module configuration")

    # Source tracking
    defined_in: str = Field(description="Which bundle defined this module")
    overridden: bool = Field(default=False, description="Whether this is overridden in the current bundle")
    override_in: str | None = Field(default=None, description="Which bundle overrides this (if overridden)")
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


class BundleListItem(CamelCaseModel):
    """Bundle list item with summary information."""

    name: str = Field(description="Bundle name")
    version: str = Field(default="1.0.0", description="Bundle version")
    description: str | None = Field(default=None, description="Bundle description")
    source: str = Field(description="Bundle source: 'user' or 'system'")
    path: str = Field(description="Path to bundle file")

    # Quick stats
    provider_count: int = Field(default=0, description="Number of providers")
    tool_count: int = Field(default=0, description="Number of tools")
    hook_count: int = Field(default=0, description="Number of hooks")
    agent_count: int = Field(default=0, description="Number of agents")

    # Composition
    includes: list[str] = Field(default_factory=list, description="Included bundle references")


class BundleDetails(CamelCaseModel):
    """Full bundle details (raw structure)."""

    name: str = Field(description="Bundle name")
    version: str = Field(default="1.0.0", description="Bundle version")
    description: str | None = Field(default=None, description="Bundle description")
    source: str = Field(description="Bundle source: 'user' or 'system'")
    path: str = Field(description="Path to bundle file")

    # Quick stats
    provider_count: int = Field(default=0, description="Number of providers")
    tool_count: int = Field(default=0, description="Number of tools")
    hook_count: int = Field(default=0, description="Number of hooks")
    agent_count: int = Field(default=0, description="Number of agents")

    # Composition
    includes: list[str] = Field(default_factory=list, description="Included bundle references")

    # Full structure
    session: SessionConfigRef | None = Field(default=None, description="Session configuration")
    providers: list[ModuleRef] = Field(default_factory=list, description="Provider modules")
    tools: list[ModuleRef] = Field(default_factory=list, description="Tool modules")
    hooks: list[ModuleRef] = Field(default_factory=list, description="Hook modules")
    agents: list[ModuleRef] = Field(default_factory=list, description="Agent modules")
    context: dict[str, str] = Field(default_factory=dict, description="Context file mappings")
    instruction: str | None = Field(default=None, description="System instruction (markdown body)")


class ResolvedBundle(CamelCaseModel):
    """Flattened bundle with source tracking.

    This is the resolved view showing what will actually run,
    with tracking of which bundle contributed each component.
    """

    name: str = Field(description="Bundle name")
    source: str = Field(description="Bundle source: 'user' or 'system'")
    includes_chain: list[str] = Field(
        default_factory=list, description="Full includes chain (e.g., ['foundation/base', 'basic', 'my-bundle'])"
    )

    # Resolved sections with source tracking
    session: ResolvedSessionConfig | None = Field(default=None, description="Session configuration with source")
    providers: list[ResolvedModuleRef] = Field(default_factory=list, description="Provider modules with source")
    tools: list[ResolvedModuleRef] = Field(default_factory=list, description="Tool modules with source")
    hooks: list[ResolvedModuleRef] = Field(default_factory=list, description="Hook modules with source")
    agents: list[ResolvedModuleRef] = Field(default_factory=list, description="Agent modules with source")

    # Content from final bundle
    instruction: str | None = Field(default=None, description="System instruction")


class BundleSource(CamelCaseModel):
    """Raw bundle source content."""

    name: str = Field(description="Bundle name")
    content: str = Field(description="Raw bundle file content")
    path: str = Field(description="Path to bundle file")
    format: str = Field(description="File format: 'md', 'yaml', or 'directory'")


class CreateBundleRequest(CamelCaseModel):
    """Request to create a new bundle."""

    name: str = Field(pattern=r"^[a-z0-9-]+$", description="Bundle name (kebab-case)")
    base_bundle: str | None = Field(default=None, description="Bundle to extend (creates include)")
    description: str | None = Field(default=None, description="Bundle description")


class CopyBundleRequest(CamelCaseModel):
    """Request to copy a bundle."""

    new_name: str = Field(pattern=r"^[a-z0-9-]+$", description="New bundle name (kebab-case)")


class UpdateBundleRequest(CamelCaseModel):
    """Request to update a bundle."""

    content: str = Field(description="Raw bundle content (markdown with YAML frontmatter)")
