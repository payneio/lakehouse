"""Mount plan data models for amplifierd.

This module defines the data structures for mount plans - complete specifications
of how to assemble a session from cached profile resources. Mount plans include
both embedded content (agents, context) and referenced modules (providers, tools, hooks).

Architecture:
    - Two mount types: EmbeddedMount (text content) vs ReferencedMount (code modules)
    - Discriminated union on mount_type field for type safety
    - Module ID collision handling via deterministic counter-based resolution
    - Format versioning for backwards compatibility
"""

from typing import Annotated
from typing import Any
from typing import Literal
from typing import Union

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class EmbeddedMount(CamelCaseModel):
    """Mount point for agents and context with embedded content.

    Used for text-based resources that LLMs consume directly. The content
    is embedded in the mount plan so it's immediately available for LLM
    processing without requiring file I/O at runtime.

    Attributes:
        mount_type: Always "embedded" for this mount type
        module_id: Unique identifier in format {profile}.{type}.{name}
        module_type: Type of module - either "agent" or "context"
        content: Full markdown/text content (NOT a file path)
        metadata: Additional metadata for the module (tags, version, etc.)

    Example:
        >>> mount = EmbeddedMount(
        ...     module_id="foundation.agent.zen-architect",
        ...     module_type="agent",
        ...     content="# Zen Architect\\n\\nYou are a systems architect...",
        ...     metadata={"version": "1.0", "tags": ["design", "architecture"]}
        ... )
    """

    mount_type: Literal["embedded"] = "embedded"
    module_id: str = Field(description="Unique module ID: {profile}.{type}.{name}")
    module_type: Literal["agent", "context"] = Field(description="Type of embedded module")
    content: str = Field(description="Full text content for LLM consumption")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (tags, version, etc.)",
    )


class ReferencedMount(CamelCaseModel):
    """Mount point for code modules with file path reference.

    Used for executable modules (Python code) that are loaded at runtime.
    The source_path points to the cached file, which the module loader
    will import when the session initializes.

    Attributes:
        mount_type: Always "referenced" for this mount type
        module_id: Unique identifier in format {profile}.{type}.{name}
        module_type: Type of module - "provider", "tool", or "hook"
        source_path: file:// URL to the cached module file
        metadata: Additional metadata for the module (version, config, etc.)

    Example:
        >>> mount = ReferencedMount(
        ...     module_id="foundation.provider.anthropic",
        ...     module_type="provider",
        ...     source_path="file:///home/user/.amplifierd/share/profiles/foundation/base/providers/anthropic.py",
        ...     metadata={"version": "2.0", "config": {"api_key": "$ANTHROPIC_API_KEY"}}
        ... )
    """

    mount_type: Literal["referenced"] = "referenced"
    module_id: str = Field(description="Unique module ID: {profile}.{type}.{name}")
    module_type: Literal["orchestrator", "context-manager", "provider", "tool", "hook"] = Field(
        description="Type of referenced module"
    )
    source_path: str = Field(description="file:// URL to cached module")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (version, config, etc.)",
    )


# Discriminated union type for type safety
# Pydantic automatically routes to correct model based on mount_type field
MountPoint = Annotated[
    Union[EmbeddedMount, ReferencedMount],
    Field(discriminator="mount_type"),
]


class SessionConfig(CamelCaseModel):
    """Session configuration and metadata.

    Contains the session-level settings and context needed to initialize
    an amplifier-core session from a mount plan.

    Attributes:
        session_id: Unique session identifier (UUID)
        profile_id: Profile used to generate this mount plan
        parent_session_id: Parent session ID for sub-sessions/delegation
        settings: Session-level settings (max_turns, streaming, etc.)
        created_at: ISO format datetime when session was created

    Example:
        >>> config = SessionConfig(
        ...     session_id="sess_abc123",
        ...     profile_id="foundation.base",
        ...     parent_session_id=None,
        ...     settings={"max_turns": 10, "streaming": True},
        ...     created_at="2025-01-25T10:30:00Z"
        ... )
    """

    session_id: str = Field(description="Unique session identifier")
    profile_id: str = Field(description="Profile ID that generated this mount plan")
    parent_session_id: str | None = Field(
        default=None,
        description="Parent session ID for sub-sessions",
    )
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Session-level settings and configuration",
    )
    created_at: str = Field(description="ISO format datetime of session creation")


class MountPlan(CamelCaseModel):
    """Complete mount plan for a session.

    A mount plan is the complete specification of how to assemble a session
    from cached profile resources. It includes both embedded content (agents,
    context) and referenced modules (providers, tools, hooks), along with
    session configuration.

    The mount points are stored as a flat list and automatically organized
    into typed dictionaries for convenient access by module type.

    Attributes:
        format_version: Version string for backwards compatibility
        session: Session configuration and metadata
        mount_points: Flat list of all mount points (embedded + referenced)
        orchestrator: Orchestrator configuration (computed)
        context: Context modules organized by module_id (computed)
        agents: Agent modules organized by module_id (computed)
        profiles: Profile modules organized by module_id (computed)
        providers: Provider modules organized by module_id (computed)
        tools: Tool modules organized by module_id (computed)
        hooks: Hook modules organized by module_id (computed)

    Example:
        >>> plan = MountPlan(
        ...     session=session_config,
        ...     mount_points=[agent_mount, provider_mount]
        ... )
        >>> # Organized dictionaries are automatically populated
        >>> assert "foundation.agent.zen-architect" in plan.agents
    """

    format_version: str = Field(
        default="1.0",
        description="Mount plan format version for backwards compatibility",
    )
    session: SessionConfig = Field(description="Session configuration and metadata")
    mount_points: list[MountPoint] = Field(
        default_factory=list,
        description="Flat list of all mount points (embedded + referenced)",
    )

    # Organized views - computed from mount_points in model_post_init
    orchestrator: dict[str, Any] | None = Field(
        default=None,
        description="Orchestrator configuration (computed from mount_points)",
    )
    context_manager: dict[str, Any] | None = Field(
        default=None,
        description="Context manager configuration (computed from mount_points)",
    )
    context: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Embedded context content organized by module_id (computed)",
    )
    agents: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Agent modules organized by module_id (computed)",
    )
    profiles: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Profile modules organized by module_id (computed)",
    )
    providers: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Provider modules organized by module_id (computed)",
    )
    tools: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Tool modules organized by module_id (computed)",
    )
    hooks: dict[str, MountPoint] = Field(
        default_factory=dict,
        description="Hook modules organized by module_id (computed)",
    )

    def model_post_init(self, __context: Any) -> None:
        """Organize mount points by module type after model initialization.

        This hook runs after Pydantic validates the model. It populates the
        organized dictionaries (agents, context, providers, etc.) by grouping
        the flat mount_points list by module_type.

        Args:
            __context: Pydantic context (unused)
        """
        self._organize_mount_points()

    def _organize_mount_points(self) -> None:
        """Group mount points by module type for convenient access.

        Iterates through the flat mount_points list and populates the typed
        dictionaries (agents, context, providers, tools, hooks) and the
        orchestrator configuration based on each mount point's module_type field.

        Module IDs are used as dictionary keys for O(1) lookup.

        Note:
            - profiles are not implemented yet (reserved for future)
            - Existing entries in organized dicts are preserved (useful for testing)
        """
        for mount in self.mount_points:
            # EmbeddedMount types (agents, context)
            if mount.module_type == "agent":
                self.agents[mount.module_id] = mount
            elif mount.module_type == "context":
                self.context[mount.module_id] = mount

            # Orchestrator (referenced module, but stored as single config not dict)
            elif mount.module_type == "orchestrator":
                # Store orchestrator mount as the orchestrator configuration
                self.orchestrator = {
                    "module": mount.module_id,
                    "source": mount.source_path,
                    "config": mount.metadata.get("config", {}),
                }

            # Context manager (referenced module, stored as single config)
            elif mount.module_type == "context-manager":
                # Store context-manager mount as the context_manager configuration
                self.context_manager = {
                    "module": mount.module_id,
                    "source": mount.source_path,
                    "config": mount.metadata.get("config", {}),
                }

            # ReferencedMount types (providers, tools, hooks)
            elif mount.module_type == "provider":
                self.providers[mount.module_id] = mount
            elif mount.module_type == "tool":
                self.tools[mount.module_id] = mount
            elif mount.module_type == "hook":
                self.hooks[mount.module_id] = mount

            # Future support for profiles
            # This is a placeholder for when that feature is implemented


class MountPlanRequest(CamelCaseModel):
    """Request to generate a mount plan from a cached profile.

    This is the input model for the mount plan generation API. It specifies
    which profile to use and any session-specific customizations.

    Attributes:
        profile_id: ID of the cached profile to use
        amplified_dir: Absolute path to amplified directory (for @mention resolution)
        session_id: Optional explicit session ID (generated if not provided)
        parent_session_id: Parent session for sub-sessions/delegation
        settings_overrides: Session-specific settings that override profile defaults
        agent_overlay: Optional agent customizations for sub-sessions

    Example:
        >>> request = MountPlanRequest(
        ...     profile_id="foundation.base",
        ...     amplified_dir="/data/projects/my-project",
        ...     session_id="sess_abc123",
        ...     settings_overrides={"max_turns": 20, "streaming": False}
        ... )
    """

    profile_id: str = Field(description="Profile ID to generate mount plan from")
    amplified_dir: str = Field(description="Absolute path to amplified directory (for @mention resolution)")
    session_id: str | None = Field(
        default=None,
        description="Explicit session ID (auto-generated if not provided)",
    )
    parent_session_id: str | None = Field(
        default=None,
        description="Parent session ID for sub-sessions/delegation",
    )
    settings_overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Session-specific settings overriding profile defaults",
    )
    agent_overlay: dict[str, Any] | None = Field(
        default=None,
        description="Agent customizations for sub-sessions (future feature)",
    )


class MountPlanSummary(CamelCaseModel):
    """Lightweight summary of a mount plan for listing operations.

    Used for efficient listing of mount plans without loading full content.
    Contains only the essential metadata needed for display and filtering.

    Attributes:
        session_id: Session identifier
        profile_id: Profile used for this mount plan
        created_at: ISO format datetime of creation
        mount_point_count: Total number of mount points
        module_types: Count of each module type (e.g., {"agent": 3, "provider": 2})

    Example:
        >>> summary = MountPlanSummary(
        ...     session_id="sess_abc123",
        ...     profile_id="foundation.base",
        ...     created_at="2025-01-25T10:30:00Z",
        ...     mount_point_count=15,
        ...     module_types={"agent": 5, "context": 2, "provider": 3, "tool": 4, "hook": 1}
        ... )
    """

    session_id: str = Field(description="Session identifier")
    profile_id: str = Field(description="Profile ID used for this mount plan")
    created_at: str = Field(description="ISO format datetime of creation")
    mount_point_count: int = Field(description="Total number of mount points")
    module_types: dict[str, int] = Field(
        default_factory=dict,
        description="Count of each module type (e.g., {'agent': 3, 'provider': 2})",
    )
