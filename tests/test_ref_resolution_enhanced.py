"""Test enhanced RefResolutionService with git subpath support."""

from pathlib import Path
from unittest.mock import patch

import pytest

from amplifierd.services.ref_resolution import RefResolutionError
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def ref_service(tmp_path: Path) -> RefResolutionService:
    """Create RefResolutionService for testing."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    return RefResolutionService(state_dir=state_dir)


def test_resolve_git_ref_with_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with repo-relative path (after @ref/)."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    # Create mock asset at subpath
    agent_dir = mock_repo_path / "agents"
    agent_dir.mkdir()
    agent_file = agent_dir / "researcher.md"
    agent_file.write_text("# Researcher Agent")

    with patch.object(ref_service, "_fetch_git", return_value=mock_repo_path):
        # Test git ref with repo-relative path: git+URL@ref/path/to/file
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main/agents/researcher.md")

        assert result == agent_file
        assert result.exists()


def test_resolve_git_ref_without_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref without subpath (repo root)."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    # Create some content at repo root
    readme = mock_repo_path / "README.md"
    readme.write_text("# Test Repo")

    with patch.object(ref_service, "_fetch_git", return_value=mock_repo_path):
        # Test git ref without subpath
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main")

        assert result == mock_repo_path
        assert result.exists()


def test_resolve_git_ref_missing_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with non-existent subpath."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    with (
        patch.object(ref_service, "_fetch_git", return_value=mock_repo_path),
        pytest.raises(RefResolutionError, match="Asset not found"),
    ):
        ref_service.resolve_ref("git+https://github.com/org/repo@main/missing/path.md")


def test_resolve_absolute_path(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving absolute path."""
    # Create test file
    test_file = tmp_path / "test.md"
    test_file.write_text("# Test")

    result = ref_service.resolve_ref(str(test_file))

    assert result == test_file
    assert result.exists()


def test_resolve_absolute_path_not_exists(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving non-existent absolute path."""
    missing_file = tmp_path / "missing.md"

    with pytest.raises(RefResolutionError, match="Absolute path does not exist"):
        ref_service.resolve_ref(str(missing_file))


def test_resolve_git_ref_with_subdirectory_syntax(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with #subdirectory= syntax."""
    # Mock _fetch_git to return subdirectory path
    mock_subdir_path = tmp_path / "subdirectory"
    mock_subdir_path.mkdir(parents=True)

    # Create test file in subdirectory
    test_file = mock_subdir_path / "test.md"
    test_file.write_text("# Test content")

    with patch.object(ref_service, "_fetch_git", return_value=mock_subdir_path):
        # Test with #subdirectory= syntax
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main#subdirectory=packages/tools")

        assert result == mock_subdir_path
        assert result.exists()


def test_resolve_git_ref_missing_at_symbol(ref_service: RefResolutionService) -> None:
    """Test git ref without @ref fails with clear error."""
    with pytest.raises(RefResolutionError, match="Invalid git ref format.*missing @ref"):
        ref_service.resolve_ref("git+https://github.com/org/repo")
