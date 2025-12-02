"""Unit tests for mount plan models."""

import pytest
from pydantic import ValidationError

from amplifierd.models.mount_plans import EmbeddedMount
from amplifierd.models.mount_plans import MountPlan
from amplifierd.models.mount_plans import MountPlanRequest
from amplifierd.models.mount_plans import MountPlanSummary
from amplifierd.models.mount_plans import ReferencedMount
from amplifierd.models.mount_plans import SessionConfig


class TestEmbeddedMount:
    """Tests for EmbeddedMount model."""

    def test_valid_creation_agent(self) -> None:
        """Test creating valid agent mount."""
        mount = EmbeddedMount(
            module_id="foundation.agent.zen-architect",
            module_type="agent",
            content="# Zen Architect\n\nYou are a systems architect...",
            metadata={"version": "1.0", "tags": ["design", "architecture"]},
        )

        assert mount.mount_type == "embedded"
        assert mount.module_id == "foundation.agent.zen-architect"
        assert mount.module_type == "agent"
        assert mount.content.startswith("# Zen Architect")
        assert mount.metadata["version"] == "1.0"

    def test_valid_creation_context(self) -> None:
        """Test creating valid context mount."""
        mount = EmbeddedMount(
            module_id="foundation.context.design-principles",
            module_type="context",
            content="# Design Principles\n\nFollow these principles...",
        )

        assert mount.mount_type == "embedded"
        assert mount.module_type == "context"
        assert mount.metadata == {}  # Default empty dict

    def test_invalid_module_type(self) -> None:
        """Test that invalid module_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddedMount(
                module_id="test.invalid.module",
                module_type="provider",  # type: ignore - intentionally wrong
                content="Test content",
            )

        error = exc_info.value
        assert "module_type" in str(error)

    def test_missing_required_fields(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddedMount()  # type: ignore - intentionally missing fields

        error = exc_info.value
        # CamelCase model uses camelCase field names in errors
        assert "moduleId" in str(error) or "module_id" in str(error)
        assert "moduleType" in str(error) or "module_type" in str(error)
        assert "content" in str(error)


class TestReferencedMount:
    """Tests for ReferencedMount model."""

    def test_valid_creation_provider(self) -> None:
        """Test creating valid provider mount."""
        mount = ReferencedMount(
            module_id="foundation.provider.anthropic",
            module_type="provider",
            source_path="file:///home/user/.amplifierd/share/profiles/foundation/base/providers/anthropic.py",
            metadata={"version": "2.0", "config": {"api_key": "$ANTHROPIC_API_KEY"}},
        )

        assert mount.mount_type == "referenced"
        assert mount.module_id == "foundation.provider.anthropic"
        assert mount.module_type == "provider"
        assert mount.source_path.startswith("file://")
        assert mount.metadata["version"] == "2.0"

    def test_valid_creation_tool(self) -> None:
        """Test creating valid tool mount."""
        mount = ReferencedMount(
            module_id="foundation.tool.file-reader",
            module_type="tool",
            source_path="file:///home/user/.amplifierd/share/profiles/foundation/base/tools/file_reader.py",
        )

        assert mount.mount_type == "referenced"
        assert mount.module_type == "tool"
        assert mount.metadata == {}

    def test_valid_creation_hook(self) -> None:
        """Test creating valid hook mount."""
        mount = ReferencedMount(
            module_id="foundation.hook.pre-commit",
            module_type="hook",
            source_path="file:///home/user/.amplifierd/share/profiles/foundation/base/hooks/pre_commit.py",
        )

        assert mount.mount_type == "referenced"
        assert mount.module_type == "hook"

    def test_invalid_module_type(self) -> None:
        """Test that invalid module_type raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ReferencedMount(
                module_id="test.invalid.module",
                module_type="agent",  # type: ignore - intentionally wrong
                source_path="file:///test/path.py",
            )

        error = exc_info.value
        assert "module_type" in str(error)


class TestSessionConfig:
    """Tests for SessionConfig model."""

    def test_valid_creation(self) -> None:
        """Test creating valid session config."""
        config = SessionConfig(
            session_id="sess_abc123",
            profile_id="foundation.base",
            parent_session_id=None,
            settings={"max_turns": 10, "streaming": True},
            created_at="2025-01-25T10:30:00Z",
        )

        assert config.session_id == "sess_abc123"
        assert config.profile_id == "foundation.base"
        assert config.parent_session_id is None
        assert config.settings["max_turns"] == 10
        assert config.created_at == "2025-01-25T10:30:00Z"

    def test_with_parent_session(self) -> None:
        """Test session config with parent session ID."""
        config = SessionConfig(
            session_id="sess_child",
            profile_id="foundation.base",
            parent_session_id="sess_parent",
            settings={},
            created_at="2025-01-25T10:30:00Z",
        )

        assert config.parent_session_id == "sess_parent"

    def test_default_empty_settings(self) -> None:
        """Test that settings default to empty dict."""
        config = SessionConfig(
            session_id="sess_123",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
        )

        assert config.settings == {}


class TestMountPlan:
    """Tests for MountPlan model and organization logic."""

    def test_empty_mount_plan(self) -> None:
        """Test creating mount plan with no mount points."""
        session_config = SessionConfig(
            session_id="sess_empty",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[],
        )

        assert plan.format_version == "1.0"
        assert plan.session.session_id == "sess_empty"
        assert len(plan.mount_points) == 0
        assert len(plan.agents) == 0
        assert len(plan.context) == 0
        assert len(plan.providers) == 0
        assert len(plan.tools) == 0
        assert len(plan.hooks) == 0

    def test_organization_agents_and_context(self) -> None:
        """Test that agents and context are organized correctly."""
        agent_mount = EmbeddedMount(
            module_id="foundation.agent.zen-architect",
            module_type="agent",
            content="# Agent content",
        )
        context_mount = EmbeddedMount(
            module_id="foundation.context.design-principles",
            module_type="context",
            content="# Context content",
        )

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[agent_mount, context_mount],
        )

        # Check flat list
        assert len(plan.mount_points) == 2

        # Check organized dicts
        assert len(plan.agents) == 1
        assert "foundation.agent.zen-architect" in plan.agents
        assert plan.agents["foundation.agent.zen-architect"] == agent_mount

        assert len(plan.context) == 1
        assert "foundation.context.design-principles" in plan.context
        assert plan.context["foundation.context.design-principles"] == context_mount

    def test_organization_providers_tools_hooks(self) -> None:
        """Test that providers, tools, and hooks are organized correctly."""
        provider_mount = ReferencedMount(
            module_id="foundation.provider.anthropic",
            module_type="provider",
            source_path="file:///test/provider.py",
        )
        tool_mount = ReferencedMount(
            module_id="foundation.tool.file-reader",
            module_type="tool",
            source_path="file:///test/tool.py",
        )
        hook_mount = ReferencedMount(
            module_id="foundation.hook.pre-commit",
            module_type="hook",
            source_path="file:///test/hook.py",
        )

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[provider_mount, tool_mount, hook_mount],
        )

        # Check flat list
        assert len(plan.mount_points) == 3

        # Check organized dicts
        assert len(plan.providers) == 1
        assert "foundation.provider.anthropic" in plan.providers

        assert len(plan.tools) == 1
        assert "foundation.tool.file-reader" in plan.tools

        assert len(plan.hooks) == 1
        assert "foundation.hook.pre-commit" in plan.hooks

    def test_mixed_mount_types(self) -> None:
        """Test mount plan with mixed embedded and referenced mounts."""
        agent = EmbeddedMount(
            module_id="foundation.agent.test",
            module_type="agent",
            content="Agent",
        )
        provider = ReferencedMount(
            module_id="foundation.provider.test",
            module_type="provider",
            source_path="file:///test.py",
        )

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[agent, provider],
        )

        assert len(plan.mount_points) == 2
        assert len(plan.agents) == 1
        assert len(plan.providers) == 1

    def test_organization_runs_on_init(self) -> None:
        """Test that _organize_mount_points runs during model_post_init."""
        agent = EmbeddedMount(
            module_id="test.agent.foo",
            module_type="agent",
            content="Test",
        )

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="test.profile",
            created_at="2025-01-25T10:30:00Z",
        )

        # Organization should happen automatically on creation
        plan = MountPlan(
            session=session_config,
            mount_points=[agent],
        )

        # Verify organization happened
        assert "test.agent.foo" in plan.agents
        assert plan.agents["test.agent.foo"] == agent


class TestMountPlanRequest:
    """Tests for MountPlanRequest model."""

    def test_minimal_request(self) -> None:
        """Test request with only required fields."""
        request = MountPlanRequest(profile_id="foundation.base", amplified_dir="/tmp/test")

        assert request.profile_id == "foundation.base"
        assert request.amplified_dir == "/tmp/test"
        assert request.session_id is None
        assert request.parent_session_id is None
        assert request.settings_overrides == {}
        assert request.agent_overlay is None

    def test_full_request(self) -> None:
        """Test request with all fields."""
        request = MountPlanRequest(
            profile_id="foundation.base",
            amplified_dir="/tmp/test",
            session_id="sess_custom",
            parent_session_id="sess_parent",
            settings_overrides={"max_turns": 20, "streaming": False},
            agent_overlay={"custom": "config"},
        )

        assert request.profile_id == "foundation.base"
        assert request.amplified_dir == "/tmp/test"
        assert request.session_id == "sess_custom"
        assert request.parent_session_id == "sess_parent"
        assert request.settings_overrides["max_turns"] == 20
        assert request.agent_overlay == {"custom": "config"}


class TestMountPlanSummary:
    """Tests for MountPlanSummary model."""

    def test_valid_creation(self) -> None:
        """Test creating mount plan summary."""
        summary = MountPlanSummary(
            session_id="sess_abc123",
            profile_id="foundation.base",
            created_at="2025-01-25T10:30:00Z",
            mount_point_count=15,
            module_types={"agent": 5, "context": 2, "provider": 3, "tool": 4, "hook": 1},
        )

        assert summary.session_id == "sess_abc123"
        assert summary.profile_id == "foundation.base"
        assert summary.mount_point_count == 15
        assert summary.module_types["agent"] == 5
        assert sum(summary.module_types.values()) == 15

    def test_empty_module_types(self) -> None:
        """Test summary with no module types."""
        summary = MountPlanSummary(
            session_id="sess_empty",
            profile_id="test.profile",
            created_at="2025-01-25T10:30:00Z",
            mount_point_count=0,
            module_types={},
        )

        assert summary.mount_point_count == 0
        assert summary.module_types == {}


class TestDiscriminatedUnion:
    """Tests for mount_type discriminated union routing."""

    def test_embedded_mount_routing(self) -> None:
        """Test that mount_type='embedded' routes to EmbeddedMount."""
        data = {
            "mount_type": "embedded",
            "module_id": "test.agent.foo",
            "module_type": "agent",
            "content": "Test content",
        }

        # Parse as MountPlan to test discriminated union
        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="test",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[data],  # type: ignore - testing runtime behavior
        )

        mount = plan.mount_points[0]
        assert isinstance(mount, EmbeddedMount)
        assert mount.mount_type == "embedded"

    def test_referenced_mount_routing(self) -> None:
        """Test that mount_type='referenced' routes to ReferencedMount."""
        data = {
            "mount_type": "referenced",
            "module_id": "test.provider.foo",
            "module_type": "provider",
            "source_path": "file:///test.py",
        }

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="test",
            created_at="2025-01-25T10:30:00Z",
        )

        plan = MountPlan(
            session=session_config,
            mount_points=[data],  # type: ignore - testing runtime behavior
        )

        mount = plan.mount_points[0]
        assert isinstance(mount, ReferencedMount)
        assert mount.mount_type == "referenced"

    def test_invalid_mount_type(self) -> None:
        """Test that invalid mount_type raises ValidationError."""
        data = {
            "mount_type": "invalid",
            "module_id": "test.foo.bar",
            "module_type": "agent",
            "content": "Test",
        }

        session_config = SessionConfig(
            session_id="sess_123",
            profile_id="test",
            created_at="2025-01-25T10:30:00Z",
        )

        with pytest.raises(ValidationError) as exc_info:
            MountPlan(
                session=session_config,
                mount_points=[data],  # type: ignore - testing runtime behavior
            )

        error = exc_info.value
        assert "mount_type" in str(error)
