"""Tests for ProfileCompilationService."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from amplifierd.models.profiles import ModuleConfig
from amplifierd.models.profiles import ProfileDetails
from amplifierd.services.profile_compilation import ProfileCompilationError
from amplifierd.services.profile_compilation import ProfileCompilationService
from amplifierd.services.profile_compilation import RefResolutionError
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Create temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def mock_fetch_service() -> Mock:
    """Create mock RefResolutionService."""
    return Mock(spec=RefResolutionService)


@pytest.fixture
def compilation_service(temp_state_dir: Path, mock_fetch_service: Mock) -> ProfileCompilationService:
    """Create ProfileCompilationService with mocked dependencies."""
    return ProfileCompilationService(temp_state_dir, mock_fetch_service)


@pytest.fixture
def sample_profile() -> ProfileDetails:
    """Create sample schema v2 profile for testing."""
    return ProfileDetails(
        name="test-profile",
        schema_version=2,
        version="1.0.0",
        description="Test profile",
        collection_id="test-collection",
        source="test",
        is_active=False,
        agents={
            "agent1": "git+https://github.com/org/repo@main/agents/agent1.md",
            "agent2": "git+https://github.com/org/repo@main/agents/agent2.md",
        },
        context={"project-docs": "git+https://github.com/org/repo@main/context-docs"},
        providers=[
            ModuleConfig(
                module="provider-anthropic",
                source="git+https://github.com/org/repo@main/providers/anthropic.py",
            )
        ],
        tools=[
            ModuleConfig(module="tool-bash", source="git+https://github.com/org/repo@main/tools/bash.py"),
            ModuleConfig(module="tool-fs", source="/absolute/path/to/tool.py"),
        ],
        hooks=[],
    )


class TestProfileCompilationService:
    """Tests for ProfileCompilationService."""

    def test_init_creates_directories(self, temp_state_dir: Path, mock_fetch_service: Mock) -> None:
        """Test initialization creates required directories."""
        service = ProfileCompilationService(temp_state_dir, mock_fetch_service)

        assert service.share_dir == temp_state_dir
        assert service.profiles_dir == temp_state_dir / "profiles"
        assert service.profiles_dir.exists()

    def test_compile_profile_uses_profile_name(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test that compilation uses profile name as directory (not random UID)."""
        # Create mock assets for agents, context, providers, tools
        agent1 = tmp_path / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = tmp_path / "agent2.md"
        agent2.write_text("# Agent 2")

        context_dir = tmp_path / "context-docs"
        context_dir.mkdir()
        (context_dir / "doc1.md").write_text("# Doc 1")

        provider = tmp_path / "provider.py"
        provider.write_text("# Provider")

        tool1 = tmp_path / "bash.py"
        tool1.write_text("# Bash tool")
        tool2 = tmp_path / "tool.py"
        tool2.write_text("# FS tool")

        # Mock ref resolution
        def mock_resolve(ref: str, ref_type: str) -> Path:
            if "agent1" in ref:
                return agent1
            if "agent2" in ref:
                return agent2
            if "context-docs" in ref:
                return context_dir
            if "anthropic" in ref:
                return provider
            if "bash" in ref:
                return tool1
            if "tool.py" in ref:
                return tool2
            raise ValueError(f"Unexpected ref: {ref}")

        compilation_service._resolve_ref = Mock(side_effect=mock_resolve)  # type: ignore[method-assign]

        # Compile profile and verify it uses profile name
        compiled_path = compilation_service.compile_profile("test-collection", sample_profile)

        # Path should be: share_dir/profiles/test-collection/test-profile/
        assert compiled_path.name == "test-profile"
        assert compiled_path.parent.name == "test-collection"
        assert compiled_path.exists()

    def test_compile_profile_creates_module_structure(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test that compilation creates proper Python module structure."""
        # Create mock assets
        agent1 = tmp_path / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = tmp_path / "agent2.md"
        agent2.write_text("# Agent 2")

        context_dir = tmp_path / "context-docs"
        context_dir.mkdir()
        (context_dir / "doc1.md").write_text("# Doc 1")

        tool_file = tmp_path / "bash.py"
        tool_file.write_text("# Tool implementation")
        tool2_file = tmp_path / "tool.py"
        tool2_file.write_text("# Tool 2")
        provider_file = tmp_path / "provider.py"
        provider_file.write_text("# Provider implementation")

        # Mock _resolve_ref to return our mock assets
        def mock_resolve(ref: str, ref_type: str) -> Path:
            if ref_type == "agent":
                if "agent1" in ref:
                    return agent1
                return agent2
            if ref_type == "context":
                return context_dir
            if ref_type == "tool":
                if "bash" in ref:
                    return tool_file
                return tool2_file
            if ref_type == "provider":
                return provider_file
            raise ValueError(f"Unexpected ref_type: {ref_type}")

        compilation_service._resolve_ref = Mock(side_effect=mock_resolve)  # type: ignore[method-assign]

        # Compile profile
        compiled_path = compilation_service.compile_profile("test-collection", sample_profile)

        # Verify structure
        assert compiled_path.exists()
        assert (compiled_path / "__init__.py").exists()

        # Check all expected subdirectories exist
        for subdir in ["orchestrator", "contexts", "agents", "contexts", "tools", "hooks", "providers"]:
            subdir_path = compiled_path / subdir
            assert subdir_path.exists(), f"Missing {subdir}/ directory"
            assert (subdir_path / "__init__.py").exists(), f"Missing {subdir}/__init__.py"

        # Verify assets were copied
        assert (compiled_path / "agents" / "agent1.md").exists()
        assert (compiled_path / "agents" / "agent2.md").exists()
        # Context key in profile is "project-docs", so directory should be contexts/project-docs/
        assert (compiled_path / "contexts" / "project-docs").is_dir()
        # Tools and providers are now in module-named subdirectories
        assert (compiled_path / "tools" / "tool-bash" / "bash.py").exists()
        assert (compiled_path / "tools" / "tool-fs" / "tool.py").exists()
        assert (compiled_path / "providers" / "provider-anthropic" / "provider.py").exists()

    def test_compile_profile_cleans_up_on_failure(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails
    ) -> None:
        """Test that compilation cleans up staging directory on failure."""
        # Mock _resolve_ref to raise an error
        compilation_service._resolve_ref = Mock(side_effect=RefResolutionError("Test error"))  # type: ignore[method-assign]

        # Attempt compilation
        with pytest.raises(ProfileCompilationError):
            compilation_service.compile_profile("test-collection", sample_profile)

        # Verify no staging directories left behind
        collection_dir = compilation_service.profiles_dir / "test-collection"
        if collection_dir.exists():
            # Should not have any .staging-* directories
            staging_dirs = [d for d in collection_dir.iterdir() if d.name.startswith(".staging-")]
            assert len(staging_dirs) == 0, "Staging directory should be cleaned up on failure"

            # Should not have final profile directory either
            profile_dir = collection_dir / sample_profile.name
            assert not profile_dir.exists(), "Final profile directory should not exist after failed compilation"


class TestRefResolution:
    """Tests for _resolve_ref method."""

    def test_resolve_git_ref(
        self, compilation_service: ProfileCompilationService, tmp_path: Path, mock_fetch_service: Mock
    ) -> None:
        """Test resolving git+ refs via RefResolutionService."""
        # Create mock asset file
        asset_file = tmp_path / "researcher.md"
        asset_file.write_text("# Researcher agent")

        # Mock ref resolution service to return the asset
        mock_fetch_service.resolve_ref.return_value = asset_file

        # Resolve git ref - this now delegates entirely to RefResolutionService
        ref = "git+https://github.com/org/repo@main/agents/researcher.md"
        resolved = compilation_service._resolve_ref(ref, "agent")

        # Verify
        assert resolved == asset_file
        assert resolved.exists()
        mock_fetch_service.resolve_ref.assert_called_once_with(ref)

    def test_resolve_git_ref_missing_asset(
        self, compilation_service: ProfileCompilationService, tmp_path: Path, mock_fetch_service: Mock
    ) -> None:
        """Test resolving git ref with missing asset - RefResolutionService handles this."""
        # Mock RefResolutionService to raise error for missing asset
        from amplifierd.services.profile_compilation import RefResolutionError
        from amplifierd.services.ref_resolution import RefResolutionError as RefError

        mock_fetch_service.resolve_ref.side_effect = RefError("Asset not found")

        # Attempt to resolve git ref for non-existent asset
        ref = "git+https://github.com/org/repo@main/agents/missing.md"
        with pytest.raises((RefError, RefResolutionError)) as exc_info:
            compilation_service._resolve_ref(ref, "agent")

        assert "agent" in str(exc_info.value).lower() or "Asset not found" in str(exc_info.value)

    def test_resolve_git_ref_invalid_format_no_at(
        self, compilation_service: ProfileCompilationService, mock_fetch_service: Mock
    ) -> None:
        """Test resolving git ref with invalid format (no @ref) - RefResolutionService handles this."""
        from amplifierd.services.profile_compilation import RefResolutionError
        from amplifierd.services.ref_resolution import RefResolutionError as RefError

        mock_fetch_service.resolve_ref.side_effect = RefError("Invalid git ref format")

        ref = "git+https://github.com/org/repo/agents/agent.md"
        with pytest.raises((RefError, RefResolutionError)):
            compilation_service._resolve_ref(ref, "agent")

    def test_resolve_git_ref_without_path(
        self, compilation_service: ProfileCompilationService, tmp_path: Path, mock_fetch_service: Mock
    ) -> None:
        """Test resolving git ref without path (uses repository root)."""
        # Create mock collection at root
        mock_collection = tmp_path / "collection"
        mock_collection.mkdir()
        # Create a file at root to verify resolution
        root_file = mock_collection / "README.md"
        root_file.write_text("# Root file")

        # Mock fetch service to return our mock collection
        mock_fetch_service.resolve_ref.return_value = mock_collection

        # Resolve git ref without path
        ref = "git+https://github.com/org/repo@main"
        resolved = compilation_service._resolve_ref(ref, "module")

        # Verify resolved to repository root
        assert resolved == mock_collection
        assert resolved.exists()
        assert resolved.is_dir()
        mock_fetch_service.resolve_ref.assert_called_once_with("git+https://github.com/org/repo@main")

    def test_resolve_absolute_path(
        self, compilation_service: ProfileCompilationService, tmp_path: Path, mock_fetch_service: Mock
    ) -> None:
        """Test resolving absolute file paths."""
        # Create test file
        asset_file = tmp_path / "agents" / "custom.md"
        asset_file.parent.mkdir(parents=True)
        asset_file.write_text("# Custom agent")

        # Mock RefResolutionService to return the path
        mock_fetch_service.resolve_ref.return_value = asset_file

        # Resolve absolute path
        ref = str(asset_file)
        resolved = compilation_service._resolve_ref(ref, "agent")

        assert resolved == asset_file
        assert resolved.exists()

    def test_resolve_absolute_path_not_exists(
        self, compilation_service: ProfileCompilationService, mock_fetch_service: Mock
    ) -> None:
        """Test resolving non-existent absolute path."""
        from amplifierd.services.profile_compilation import RefResolutionError
        from amplifierd.services.ref_resolution import RefResolutionError as RefError

        mock_fetch_service.resolve_ref.side_effect = RefError("Absolute path does not exist")

        ref = "/nonexistent/path/to/agent.md"
        with pytest.raises((RefError, RefResolutionError)):
            compilation_service._resolve_ref(ref, "agent")


class TestModuleStructure:
    """Tests for _create_module_structure method."""

    def test_create_empty_structure(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test creating module structure with no assets."""
        target_dir = tmp_path / "compiled"
        target_dir.mkdir()

        assets: dict[str, list[Path]] = {
            "orchestrator": [],
            "context-manager": [],
            "agents": [],
            "context": [],
            "tools": [],
            "hooks": [],
            "providers": [],
        }

        compilation_service._create_module_structure(target_dir, assets, sample_profile)

        # Verify root __init__.py
        assert (target_dir / "__init__.py").exists()

        # Verify empty subdirectories created with __init__.py
        assert (target_dir / "tools").is_dir()
        assert (target_dir / "tools" / "__init__.py").exists()
        assert (target_dir / "hooks").is_dir()
        assert (target_dir / "hooks" / "__init__.py").exists()
        assert (target_dir / "providers").is_dir()
        assert (target_dir / "providers" / "__init__.py").exists()

    def test_copy_single_files(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test copying single file assets."""
        target_dir = tmp_path / "compiled"
        target_dir.mkdir()

        # Create test assets
        agent_file = tmp_path / "agent.md"
        agent_file.write_text("# Agent docs")

        assets: dict[str, list[Path]] = {
            "orchestrator": [],
            "context-manager": [],
            "agents": [agent_file],
            "context": [],
            "tools": [],
            "hooks": [],
            "providers": [],
        }

        compilation_service._create_module_structure(target_dir, assets, sample_profile)

        # Verify agent file copied
        assert (target_dir / "agents" / "agent.md").exists()
        assert (target_dir / "agents" / "agent.md").read_text() == "# Agent docs"

    def test_copy_directories(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test copying directory assets."""
        target_dir = tmp_path / "compiled"
        target_dir.mkdir()

        # Create test directory with files
        context_dir = tmp_path / "context-docs"
        context_dir.mkdir()
        (context_dir / "doc1.md").write_text("# Doc 1")
        (context_dir / "doc2.md").write_text("# Doc 2")
        subdir = context_dir / "subdir"
        subdir.mkdir()
        (subdir / "doc3.md").write_text("# Doc 3")

        assets: dict[str, list[Path]] = {
            "orchestrator": [],
            "context-manager": [],
            "agents": [],
            "context": [context_dir],
            "tools": [],
            "hooks": [],
            "providers": [],
        }

        compilation_service._create_module_structure(target_dir, assets, sample_profile)

        # Verify directory copied with all files
        # Uses profile key name "project-docs" not asset dir name "context-docs"
        copied_dir = target_dir / "contexts" / "project-docs"
        assert copied_dir.is_dir()
        assert (copied_dir / "doc1.md").exists()
        assert (copied_dir / "doc2.md").exists()
        assert (copied_dir / "subdir" / "doc3.md").exists()

    def test_mixed_assets(
        self, compilation_service: ProfileCompilationService, sample_profile: ProfileDetails, tmp_path: Path
    ) -> None:
        """Test copying mix of files and directories."""
        target_dir = tmp_path / "compiled"
        target_dir.mkdir()

        # Create agent files
        agent1 = tmp_path / "agent1.md"
        agent1.write_text("# Agent 1")
        agent2 = tmp_path / "agent2.md"
        agent2.write_text("# Agent 2")

        # Create context directory
        context_dir = tmp_path / "context-docs"
        context_dir.mkdir()
        (context_dir / "doc1.md").write_text("# Doc 1")
        (context_dir / "doc2.md").write_text("# Doc 2")

        assets: dict[str, list[Path]] = {
            "orchestrator": [],
            "context-manager": [],
            "agents": [agent1, agent2],
            "context": [context_dir],
            "tools": [],
            "hooks": [],
            "providers": [],
        }

        compilation_service._create_module_structure(target_dir, assets, sample_profile)

        # Verify all assets copied
        assert (target_dir / "agents" / "agent1.md").exists()
        assert (target_dir / "agents" / "agent2.md").exists()
        # Uses profile key name "project-docs" from sample_profile fixture
        assert (target_dir / "contexts" / "project-docs").is_dir()
        assert (target_dir / "contexts" / "project-docs" / "doc1.md").exists()
        assert (target_dir / "contexts" / "project-docs" / "doc2.md").exists()
