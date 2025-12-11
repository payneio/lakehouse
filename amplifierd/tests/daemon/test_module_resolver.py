"""Tests for DaemonModuleSourceResolver (v3)."""

import pytest

from amplifierd.module_resolver import DaemonModuleSourceResolver, ModuleSource


@pytest.fixture
def mock_share_dir(tmp_path):
    """Create mock share directory structure for v3 profiles."""
    share_dir = tmp_path / "share"

    # Create v3 profile structure (flat, no collections)
    profile_dir = share_dir / "profiles" / "test-profile"
    profile_dir.mkdir(parents=True)

    # Create session components
    (profile_dir / "session" / "orchestrator" / "loop-streaming").mkdir(parents=True)
    (profile_dir / "session" / "context" / "context-simple").mkdir(parents=True)
    (profile_dir / "session" / "providers" / "provider-anthropic").mkdir(parents=True)

    # Create behavior components
    behavior_dir = profile_dir / "behaviors" / "command-line"
    (behavior_dir / "tools" / "tool-bash").mkdir(parents=True)
    (behavior_dir / "hooks" / "hooks-logging").mkdir(parents=True)

    return share_dir


@pytest.mark.unit
class TestDaemonModuleSourceResolver:
    """Test DaemonModuleSourceResolver (v3)."""

    def test_resolver_initialization(self, mock_share_dir):
        """Test resolver initializes with share directory."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        assert resolver.share_dir == mock_share_dir

    def test_resolve_orchestrator_from_session(self, mock_share_dir):
        """Test resolving orchestrator module from session/."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("loop-streaming", "test-profile")

        assert isinstance(source, ModuleSource)
        assert source.module_id == "loop-streaming"

        path = source.resolve()
        expected = mock_share_dir / "profiles" / "test-profile" / "session" / "orchestrator" / "loop-streaming"
        assert path == expected
        assert path.exists()

    def test_resolve_context_from_session(self, mock_share_dir):
        """Test resolving context manager module from session/."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("context-simple", "test-profile")
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "test-profile" / "session" / "context" / "context-simple"
        assert path == expected

    def test_resolve_provider_from_session(self, mock_share_dir):
        """Test resolving provider module from session/."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("provider-anthropic", "test-profile")
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "test-profile" / "session" / "providers" / "provider-anthropic"
        assert path == expected

    def test_resolve_tool_from_behavior(self, mock_share_dir):
        """Test resolving tool module from behaviors/."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("tool-bash", "test-profile")
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "test-profile" / "behaviors" / "command-line" / "tools" / "tool-bash"
        assert path == expected

    def test_resolve_hook_from_behavior(self, mock_share_dir):
        """Test resolving hook module from behaviors/."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("hooks-logging", "test-profile")
        path = source.resolve()

        expected = (
            mock_share_dir / "profiles" / "test-profile" / "behaviors" / "command-line" / "hooks" / "hooks-logging"
        )
        assert path == expected

    def test_resolve_missing_profile_hint(self, mock_share_dir):
        """Test error when profile hint is missing."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        with pytest.raises(ValueError, match="profile_hint.*required"):
            resolver.resolve("provider-anthropic", None)

    def test_resolve_nonexistent_profile(self, mock_share_dir):
        """Test error when profile doesn't exist."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        with pytest.raises(FileNotFoundError, match="Profile 'nonexistent' not found"):
            resolver.resolve("provider-anthropic", "nonexistent")

    def test_resolve_nonexistent_module(self, mock_share_dir):
        """Test error when module not found in profile."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        with pytest.raises(FileNotFoundError, match="Module 'nonexistent' not found"):
            resolver.resolve("nonexistent", "test-profile")

    def test_component_type_inference(self, mock_share_dir):
        """Test _infer_component_type method."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        assert resolver._infer_component_type("provider-anthropic") == "providers"
        assert resolver._infer_component_type("tool-bash") == "tools"
        assert resolver._infer_component_type("hooks-logging") == "hooks"
        assert resolver._infer_component_type("loop-streaming") == "orchestrator"
        assert resolver._infer_component_type("context-simple") == "context"
