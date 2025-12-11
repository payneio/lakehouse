"""Test agent ref resolution in profile compilation."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from amplifierd.models.profiles import ProfileDetails, SessionConfig, ModuleConfig
from amplifierd.services.profile_compilation import (
    ProfileCompilationService,
    ProfileCompilationError,
    RefResolutionError,
)


def test_compile_profile_resolves_agent_dict_values(tmp_path: Path):
    """Test that agent refs (dict values) are resolved, not dict keys."""
    # Setup
    share_dir = tmp_path / "share"
    share_dir.mkdir()

    # Create mock ref resolution service
    mock_ref_service = Mock()
    agent_path = tmp_path / "agent.md"
    agent_path.write_text("# Test Agent")
    mock_ref_service.resolve_ref.return_value = agent_path

    service = ProfileCompilationService(share_dir, mock_ref_service)

    # Create profile with agents dict (name -> URL mapping)
    profile = ProfileDetails(
        name="test-profile",
        version="1.0.0",
        description="Test",
        source="user",
        is_active=False,
        providers=[],
        tools=[],
        hooks=[],
        session=SessionConfig(
            orchestrator=ModuleConfig(module="test", source=None),
        ),
        agents={"explorer": "https://raw.githubusercontent.com/test/agent.md"},
    )

    # Compile profile
    compiled_path = service.compile_profile("test-collection", profile, force=True)

    # Verify agent URL was resolved (not the key "explorer")
    mock_ref_service.resolve_ref.assert_called_with(
        "https://raw.githubusercontent.com/test/agent.md"
    )

    # Verify compiled structure
    assert (compiled_path / "agents" / "agent.md").exists()


def test_compile_profile_handles_multiple_agents(tmp_path: Path):
    """Test that multiple agent refs are all resolved correctly."""
    # Setup
    share_dir = tmp_path / "share"
    share_dir.mkdir()

    # Create mock ref resolution service that returns different paths
    mock_ref_service = Mock()

    def resolve_side_effect(ref: str) -> Path:
        if "explorer" in ref:
            path = tmp_path / "explorer.md"
            path.write_text("# Explorer")
            return path
        elif "analyzer" in ref:
            path = tmp_path / "analyzer.md"
            path.write_text("# Analyzer")
            return path
        raise RefResolutionError(f"Unknown ref: {ref}")

    mock_ref_service.resolve_ref.side_effect = resolve_side_effect

    service = ProfileCompilationService(share_dir, mock_ref_service)

    # Create profile with multiple agents
    profile = ProfileDetails(
        name="test-profile",
        version="1.0.0",
        description="Test",
        source="user",
        is_active=False,
        providers=[],
        tools=[],
        hooks=[],
        session=SessionConfig(
            orchestrator=ModuleConfig(module="test", source=None),
        ),
        agents={
            "explorer": "https://example.com/explorer.md",
            "analyzer": "https://example.com/analyzer.md",
        },
    )

    # Compile profile
    compiled_path = service.compile_profile("test-collection", profile, force=True)

    # Verify both URLs were resolved
    assert mock_ref_service.resolve_ref.call_count == 2
    calls = [call[0][0] for call in mock_ref_service.resolve_ref.call_args_list]
    assert "https://example.com/explorer.md" in calls
    assert "https://example.com/analyzer.md" in calls

    # Verify both agents in compiled structure
    assert (compiled_path / "agents" / "explorer.md").exists()
    assert (compiled_path / "agents" / "analyzer.md").exists()


def test_compile_profile_fails_on_invalid_agent_ref(tmp_path: Path):
    """Test that compilation fails if agent ref cannot be resolved."""
    # Setup
    share_dir = tmp_path / "share"
    share_dir.mkdir()

    # Mock ref service that fails
    mock_ref_service = Mock()
    mock_ref_service.resolve_ref.side_effect = RefResolutionError("Resolution failed")

    service = ProfileCompilationService(share_dir, mock_ref_service)

    # Create profile with invalid agent ref
    profile = ProfileDetails(
        name="test-profile",
        version="1.0.0",
        description="Test",
        source="user",
        is_active=False,
        providers=[],
        tools=[],
        hooks=[],
        session=SessionConfig(
            orchestrator=ModuleConfig(module="test", source=None),
        ),
        agents={"bad-agent": "https://invalid.url/agent.md"},
    )

    # Compilation should fail
    with pytest.raises(ProfileCompilationError) as exc_info:
        service.compile_profile("test-collection", profile, force=True)

    # Verify error mentions the agent
    assert "bad-agent" in str(exc_info.value) or "https://invalid.url/agent.md" in str(exc_info.value)
