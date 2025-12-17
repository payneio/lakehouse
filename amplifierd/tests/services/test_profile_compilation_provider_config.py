"""Test that provider config is correctly passed through during profile compilation."""

from pathlib import Path
from unittest.mock import MagicMock


def test_provider_inline_config_preserved(tmp_path: Path) -> None:
    """Test that inline provider config from profile.yaml is preserved in mount plan."""
    from amplifierd.services.profile_compilation import ProfileCompilationService

    # Setup mock services
    share_dir = tmp_path / "share"
    cache_dir = tmp_path / "cache"
    share_dir.mkdir()
    cache_dir.mkdir()

    mock_ref_resolution = MagicMock()
    mock_registry_service = MagicMock()

    service = ProfileCompilationService(
        share_dir=share_dir,
        cache_dir=cache_dir,
        ref_resolution=mock_ref_resolution,
        registry_service=mock_registry_service,
    )

    # Create a minimal profile with inline provider config
    profile_yaml = {
        "profile": {
            "name": "test-profile",
            "schema_version": 3,
            "version": "1.0.0",
        },
        "providers": [
            {
                "id": "provider-anthropic",
                "source": "amp://test/providers/provider-anthropic",
                "config": {
                    "debug": True,
                    "raw_debug": True,
                    "default_model": "claude-sonnet-4-5",
                },
            }
        ],
    }

    # Call _generate_mount_plan directly - it doesn't need external dependencies
    mount_plan = service._generate_mount_plan(
        profile=profile_yaml,
        config={},
        asset_map={},
        behavior_defs={},
        sorted_behavior_ids=[],
    )

    # Verify provider config is preserved
    assert "providers" in mount_plan
    assert len(mount_plan["providers"]) == 1

    provider = mount_plan["providers"][0]
    assert provider["module"] == "provider-anthropic"
    assert provider["config"]["debug"] is True
    assert provider["config"]["raw_debug"] is True
    assert provider["config"]["default_model"] == "claude-sonnet-4-5"


def test_provider_config_overlay(tmp_path: Path) -> None:
    """Test that provider_config_map overlays inline config."""
    from amplifierd.services.profile_compilation import ProfileCompilationService

    share_dir = tmp_path / "share"
    cache_dir = tmp_path / "cache"
    share_dir.mkdir()
    cache_dir.mkdir()

    mock_ref_resolution = MagicMock()
    mock_registry_service = MagicMock()

    service = ProfileCompilationService(
        share_dir=share_dir,
        cache_dir=cache_dir,
        ref_resolution=mock_ref_resolution,
        registry_service=mock_registry_service,
    )

    # Profile with inline config
    profile_yaml = {
        "profile": {
            "name": "test-profile",
            "schema_version": 3,
            "version": "1.0.0",
        },
        "providers": [
            {
                "id": "provider-anthropic",
                "source": "amp://test/providers/provider-anthropic",
                "config": {
                    "debug": True,
                    "default_model": "claude-sonnet-4-5",
                },
            }
        ],
    }

    # Config with provider-specific overrides
    config = {
        "providers": {
            "provider-anthropic": {
                "debug": False,  # Override inline config
                "extra_setting": "value",  # Add new setting
            }
        }
    }

    mount_plan = service._generate_mount_plan(
        profile=profile_yaml,
        config=config,
        asset_map={},
        behavior_defs={},
        sorted_behavior_ids=[],
    )

    provider = mount_plan["providers"][0]
    # debug should be overridden to False
    assert provider["config"]["debug"] is False
    # default_model should be preserved from inline config
    assert provider["config"]["default_model"] == "claude-sonnet-4-5"
    # extra_setting should be added from config overlay
    assert provider["config"]["extra_setting"] == "value"


def test_provider_string_format(tmp_path: Path) -> None:
    """Test that string-format providers still work (backward compatibility)."""
    from amplifierd.services.profile_compilation import ProfileCompilationService

    share_dir = tmp_path / "share"
    cache_dir = tmp_path / "cache"
    share_dir.mkdir()
    cache_dir.mkdir()

    mock_ref_resolution = MagicMock()
    mock_registry_service = MagicMock()

    service = ProfileCompilationService(
        share_dir=share_dir,
        cache_dir=cache_dir,
        ref_resolution=mock_ref_resolution,
        registry_service=mock_registry_service,
    )

    # Profile with string-format provider (no inline config)
    profile_yaml = {
        "profile": {
            "name": "test-profile",
            "schema_version": 3,
            "version": "1.0.0",
        },
        "providers": ["provider-anthropic"],  # String format, not dict
    }

    # Config provides the provider settings
    config = {
        "providers": {
            "provider-anthropic": {
                "debug": True,
            }
        }
    }

    mount_plan = service._generate_mount_plan(
        profile=profile_yaml,
        config=config,
        asset_map={},
        behavior_defs={},
        sorted_behavior_ids=[],
    )

    provider = mount_plan["providers"][0]
    assert provider["module"] == "provider-anthropic"
    assert provider["config"]["debug"] is True
