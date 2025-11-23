"""Tests for module resolver service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from amplifierd.services.module_resolver_service import ModuleResolverService


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with (
        tempfile.TemporaryDirectory() as share_dir,
        tempfile.TemporaryDirectory() as state_dir,
    ):
        yield Path(share_dir), Path(state_dir)


@pytest.fixture
def service(temp_dirs):
    """Create module resolver service instance."""
    share_dir, state_dir = temp_dirs
    return ModuleResolverService(share_dir=share_dir, state_dir=state_dir)


def test_parse_module_source_basic(service: ModuleResolverService):
    """Test parsing basic git URL."""
    source = "git+https://github.com/org/repo"
    git_url, branch, subdirectory = service._parse_module_source(source)

    assert git_url == "https://github.com/org/repo"
    assert branch is None
    assert subdirectory is None


def test_parse_module_source_with_branch(service: ModuleResolverService):
    """Test parsing git URL with branch."""
    source = "git+https://github.com/org/repo@main"
    git_url, branch, subdirectory = service._parse_module_source(source)

    assert git_url == "https://github.com/org/repo"
    assert branch == "main"
    assert subdirectory is None


def test_parse_module_source_with_subdirectory(service: ModuleResolverService):
    """Test parsing git URL with subdirectory."""
    source = "git+https://github.com/org/repo#path/to/module"
    git_url, branch, subdirectory = service._parse_module_source(source)

    assert git_url == "https://github.com/org/repo"
    assert branch is None
    assert subdirectory == "path/to/module"


def test_parse_module_source_with_branch_and_subdirectory(service: ModuleResolverService):
    """Test parsing git URL with both branch and subdirectory."""
    source = "git+https://github.com/org/repo@main#path/to/module"
    git_url, branch, subdirectory = service._parse_module_source(source)

    assert git_url == "https://github.com/org/repo"
    assert branch == "main"
    assert subdirectory == "path/to/module"


def test_parse_module_source_subdirectory_format(service: ModuleResolverService):
    """Test parsing git URL with subdirectory= format."""
    source = "git+https://github.com/org/repo#subdirectory=path/to/module"
    git_url, branch, subdirectory = service._parse_module_source(source)

    assert git_url == "https://github.com/org/repo"
    assert branch is None
    assert subdirectory == "path/to/module"


@patch("subprocess.run")
def test_get_content_hash_success(mock_run, service: ModuleResolverService):
    """Test getting git commit hash."""
    mock_run.return_value = MagicMock(stdout="abc123def456ghi789\trefs/heads/main\n", returncode=0)

    result = service._get_content_hash("https://github.com/org/repo", "main")

    assert result == "abc123def456"
    mock_run.assert_called_once()


@patch("subprocess.run")
def test_get_content_hash_failure(mock_run, service: ModuleResolverService):
    """Test handling git hash failure."""
    mock_run.side_effect = Exception("Git command failed")

    result = service._get_content_hash("https://github.com/org/repo", "main")

    assert result is None


def test_create_module_symlink(service: ModuleResolverService, temp_dirs):
    """Test creating module symlink."""
    share_dir, state_dir = temp_dirs

    cache_dir = state_dir / "modules" / "abc123"
    cache_dir.mkdir(parents=True)
    (cache_dir / "provider.py").write_text("# Test module")

    target_link = share_dir / "modules" / "test-collection" / "test-module"

    service._create_module_symlink(cache_dir, target_link)

    assert target_link.is_symlink()
    assert target_link.resolve() == cache_dir
    assert (target_link / "provider.py").exists()


def test_create_module_symlink_replaces_existing(service: ModuleResolverService, temp_dirs):
    """Test that symlink creation replaces existing symlink."""
    share_dir, state_dir = temp_dirs

    old_cache = state_dir / "modules" / "old123"
    old_cache.mkdir(parents=True)

    new_cache = state_dir / "modules" / "new123"
    new_cache.mkdir(parents=True)
    (new_cache / "provider.py").write_text("# New module")

    target_link = share_dir / "modules" / "test-collection" / "test-module"
    target_link.parent.mkdir(parents=True)
    target_link.symlink_to(old_cache)

    service._create_module_symlink(new_cache, target_link)

    assert target_link.is_symlink()
    assert target_link.resolve() == new_cache
    assert (target_link / "provider.py").exists()
