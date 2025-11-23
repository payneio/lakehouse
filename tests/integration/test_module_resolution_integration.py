"""Integration test for module resolution system."""

import tempfile
from pathlib import Path

import pytest
import yaml

from amplifierd.services.module_resolver_service import ModuleResolverService
from amplifierd.services.simple_profile_service import SimpleProfileService


@pytest.fixture
def temp_structure():
    """Create temporary directory structure for testing."""
    with tempfile.TemporaryDirectory() as root_dir:
        root = Path(root_dir)

        share_dir = root / "share"
        share_dir.mkdir()
        (share_dir / "profiles").mkdir()
        (share_dir / "modules").mkdir()

        state_dir = root / "state"
        state_dir.mkdir()
        (state_dir / "modules").mkdir()

        data_dir = root / "data"
        data_dir.mkdir()

        yield {
            "root": root,
            "share": share_dir,
            "state": state_dir,
            "data": data_dir,
        }


def test_profile_service_integration(temp_structure):
    """Test profile service module sync integration."""
    share_dir = temp_structure["share"]
    data_dir = temp_structure["data"]

    collection_name = "test-collection"
    profile_dir = share_dir / "profiles" / collection_name
    profile_dir.mkdir(parents=True)

    profile_data = {
        "profile": {"name": "test-profile", "version": "1.0.0", "description": "Test profile"},
        "providers": [
            {"module": "test-provider", "source": "git+https://github.com/test/provider@main#modules/provider"}
        ],
        "tools": [{"module": "test-tool", "source": "git+https://github.com/test/tool#modules/tool"}],
    }

    profile_file = profile_dir / "test.yaml"
    with open(profile_file, "w") as f:
        yaml.dump(profile_data, f)

    profile_service = SimpleProfileService(share_dir=share_dir, data_dir=data_dir)

    profiles = profile_service.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "test-profile"

    profile = profile_service.get_profile("test-profile")
    assert profile.name == "test-profile"
    assert len(profile.providers) == 1
    assert profile.providers[0].module == "test-provider"
    assert profile.providers[0].source == "git+https://github.com/test/provider@main#modules/provider"


def test_module_resolver_creates_cache_structure(temp_structure):
    """Test that module resolver creates proper cache structure."""
    share_dir = temp_structure["share"]
    state_dir = temp_structure["state"]

    _ = ModuleResolverService(share_dir=share_dir, state_dir=state_dir)

    assert (state_dir / "modules").exists()
    assert (share_dir / "modules").exists()


def test_module_resolver_parse_sources(temp_structure):
    """Test module resolver parsing various source formats."""
    share_dir = temp_structure["share"]
    state_dir = temp_structure["state"]

    resolver = ModuleResolverService(share_dir=share_dir, state_dir=state_dir)

    test_cases = [
        (
            "git+https://github.com/org/repo",
            ("https://github.com/org/repo", None, None),
        ),
        (
            "git+https://github.com/org/repo@main",
            ("https://github.com/org/repo", "main", None),
        ),
        (
            "git+https://github.com/org/repo#path/to/module",
            ("https://github.com/org/repo", None, "path/to/module"),
        ),
        (
            "git+https://github.com/org/repo@main#path/to/module",
            ("https://github.com/org/repo", "main", "path/to/module"),
        ),
    ]

    for source, expected in test_cases:
        result = resolver._parse_module_source(source)
        assert result == expected


def test_end_to_end_profile_module_resolution(temp_structure):
    """Test end-to-end profile with module resolution (without actual git operations)."""
    share_dir = temp_structure["share"]
    data_dir = temp_structure["data"]

    collection_name = "test-collection"
    profile_dir = share_dir / "profiles" / collection_name
    profile_dir.mkdir(parents=True)

    profile_data = {
        "profile": {"name": "e2e-test", "version": "1.0.0", "description": "End-to-end test"},
        "providers": [{"module": "mock-provider"}],
        "tools": [{"module": "mock-tool", "source": None}],
    }

    profile_file = profile_dir / "e2e.yaml"
    with open(profile_file, "w") as f:
        yaml.dump(profile_data, f)

    profile_service = SimpleProfileService(share_dir=share_dir, data_dir=data_dir)

    profile = profile_service.get_profile("e2e-test")
    assert profile.name == "e2e-test"
    assert len(profile.providers) == 1
    assert len(profile.tools) == 1

    results = profile_service.sync_profile_modules("e2e-test")

    assert isinstance(results, dict)
    assert len(results) == 0
