"""Tests for LakehouseBundleManager."""

from pathlib import Path

import pytest

from lakehouse_library.bundles import LakehouseBundleManager


class TestLakehouseBundleManager:
    """Tests for LakehouseBundleManager."""

    def test_init_with_default_home(self, tmp_path: Path) -> None:
        """Manager initializes with provided home directory."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        assert manager.home_dir == tmp_path
        assert manager.bundles_dir == tmp_path / "bundles"

    def test_discover_local_bundles(self, tmp_path: Path) -> None:
        """Manager discovers bundles in bundles directory."""
        # Create a test bundle
        bundles_dir = tmp_path / "bundles"
        test_bundle = bundles_dir / "test-bundle"
        test_bundle.mkdir(parents=True)
        (test_bundle / "bundle.yaml").write_text(
            "bundle:\n  name: test-bundle\n  version: 1.0.0\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)

        # Check bundle was discovered
        assert "test-bundle" in manager.list_available_bundles()

    def test_discover_skips_non_bundles(self, tmp_path: Path) -> None:
        """Manager skips directories without bundle files."""
        bundles_dir = tmp_path / "bundles"
        not_a_bundle = bundles_dir / "not-a-bundle"
        not_a_bundle.mkdir(parents=True)
        (not_a_bundle / "random.txt").write_text("not a bundle")

        manager = LakehouseBundleManager(home_dir=tmp_path)

        assert "not-a-bundle" not in manager.list_available_bundles()

    def test_discover_single_file_bundles(self, tmp_path: Path) -> None:
        """Manager discovers single .md file bundles."""
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create a single-file bundle (like basic.md)
        (bundles_dir / "basic.md").write_text(
            "---\nbundle:\n  name: basic\n  version: 1.0.0\n---\n# Basic Bundle\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)

        assert "basic" in manager.list_available_bundles()

    def test_discover_bundles_in_share_directory(self, tmp_path: Path) -> None:
        """Manager discovers bundles in share/bundles directory."""
        share_bundles = tmp_path / "share" / "bundles"
        share_bundles.mkdir(parents=True)

        # Create a bundle in share directory
        (share_bundles / "shared-bundle.md").write_text(
            "---\nbundle:\n  name: shared-bundle\n  version: 1.0.0\n---\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)

        assert "shared-bundle" in manager.list_available_bundles()

    def test_user_bundles_override_share_bundles(self, tmp_path: Path) -> None:
        """User bundles in bundles/ take priority over share/bundles/."""
        # Create bundle in share directory
        share_bundles = tmp_path / "share" / "bundles"
        share_bundles.mkdir(parents=True)
        (share_bundles / "test-bundle.md").write_text(
            "---\nbundle:\n  name: test-bundle\n  version: 1.0.0\n---\n"
        )

        # Create same bundle in user directory
        user_bundles = tmp_path / "bundles"
        user_bundles.mkdir(parents=True)
        (user_bundles / "test-bundle.md").write_text(
            "---\nbundle:\n  name: test-bundle\n  version: 2.0.0\n---\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)

        # Should only have one entry (user takes priority)
        assert manager.list_available_bundles().count("test-bundle") == 1

    def test_discover_nested_bundles(self, tmp_path: Path) -> None:
        """Manager discovers bundles in subdirectories with prefix."""
        bundles_dir = tmp_path / "bundles"
        foundation_dir = bundles_dir / "foundation"
        foundation_dir.mkdir(parents=True)

        # Create nested bundle (like foundation/base.md)
        (foundation_dir / "base.md").write_text(
            "---\nbundle:\n  name: base\n  version: 1.0.0\n---\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)

        assert "foundation/base" in manager.list_available_bundles()

    @pytest.mark.asyncio
    async def test_load_bundle_from_well_known_path(self, tmp_path: Path) -> None:
        """Manager loads bundle from well-known bundles directory."""
        # Create a test bundle
        bundles_dir = tmp_path / "bundles"
        test_bundle = bundles_dir / "test-bundle"
        test_bundle.mkdir(parents=True)
        (test_bundle / "bundle.yaml").write_text(
            "bundle:\n  name: test-bundle\n  version: 1.0.0\n"
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        bundle = await manager.load_bundle("test-bundle")

        assert bundle.name == "test-bundle"
        assert bundle.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_bundle_to_mount_plan(self, tmp_path: Path) -> None:
        """bundle_to_mount_plan converts Bundle to dict."""
        # Create a test bundle with tools
        bundles_dir = tmp_path / "bundles"
        test_bundle = bundles_dir / "test-bundle"
        test_bundle.mkdir(parents=True)
        (test_bundle / "bundle.yaml").write_text(
            """bundle:
  name: test-bundle
  version: 1.0.0
tools:
  - module: tool-test
    config:
      setting: value
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        bundle = await manager.load_bundle("test-bundle")
        mount_plan = manager.bundle_to_mount_plan(bundle)

        assert "tools" in mount_plan
        assert len(mount_plan["tools"]) == 1
        assert mount_plan["tools"][0]["module"] == "tool-test"

    @pytest.mark.asyncio
    async def test_generate_mount_plan_injects_runtime_config(
        self, tmp_path: Path
    ) -> None:
        """generate_mount_plan injects runtime configuration."""
        # Create a test bundle with tools
        bundles_dir = tmp_path / "bundles"
        test_bundle = bundles_dir / "test-bundle"
        test_bundle.mkdir(parents=True)
        (test_bundle / "bundle.yaml").write_text(
            """bundle:
  name: test-bundle
  version: 1.0.0
tools:
  - module: tool-filesystem
    config: {}
providers:
  - module: provider-test
    config: {}
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = await manager.generate_mount_plan(
            bundle_ref="test-bundle",
            session_id="sess-123",
            project_path="/data/projects/test",
            api_key="test-api-key",
        )

        # Check working_dir injected
        assert mount_plan["tools"][0]["config"]["working_dir"] == "/data/projects/test"

        # Check allowed_write_paths injected for filesystem tool
        assert mount_plan["tools"][0]["config"]["allowed_write_paths"] == [
            "/data/projects/test"
        ]

        # Check api_key injected into providers
        assert mount_plan["providers"][0]["config"]["api_key"] == "test-api-key"

    @pytest.mark.asyncio
    async def test_generate_mount_plan_preserves_existing_config(
        self, tmp_path: Path
    ) -> None:
        """generate_mount_plan doesn't overwrite existing config values."""
        # Create a test bundle with pre-configured tools
        bundles_dir = tmp_path / "bundles"
        test_bundle = bundles_dir / "test-bundle"
        test_bundle.mkdir(parents=True)
        (test_bundle / "bundle.yaml").write_text(
            """bundle:
  name: test-bundle
  version: 1.0.0
tools:
  - module: tool-filesystem
    config:
      working_dir: /custom/path
      allowed_write_paths:
        - /custom/allowed
"""
        )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = await manager.generate_mount_plan(
            bundle_ref="test-bundle",
            session_id="sess-123",
            project_path="/data/projects/test",
        )

        # Existing config should be preserved
        assert mount_plan["tools"][0]["config"]["working_dir"] == "/custom/path"
        assert mount_plan["tools"][0]["config"]["allowed_write_paths"] == [
            "/custom/allowed"
        ]

    def test_list_available_bundles(self, tmp_path: Path) -> None:
        """list_available_bundles returns sorted list of bundle names."""
        bundles_dir = tmp_path / "bundles"

        # Create multiple bundles
        for name in ["zebra", "alpha", "middle"]:
            bundle_dir = bundles_dir / name
            bundle_dir.mkdir(parents=True)
            (bundle_dir / "bundle.yaml").write_text(
                f"bundle:\n  name: {name}\n  version: 1.0.0\n"
            )

        manager = LakehouseBundleManager(home_dir=tmp_path)
        bundles = manager.list_available_bundles()

        # Should be sorted
        assert bundles == ["alpha", "middle", "zebra"]


class TestRuntimeConfigInjection:
    """Tests for _inject_runtime_config method."""

    def test_inject_working_dir_to_all_tools(self, tmp_path: Path) -> None:
        """working_dir is injected into all tools."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = {
            "tools": [
                {"module": "tool-a", "config": {}},
                {"module": "tool-b", "config": {}},
            ]
        }

        result = manager._inject_runtime_config(
            mount_plan=mount_plan,
            session_id="sess-123",
            project_path="/test/path",
        )

        assert result["tools"][0]["config"]["working_dir"] == "/test/path"
        assert result["tools"][1]["config"]["working_dir"] == "/test/path"

    def test_inject_allowed_write_paths_only_to_filesystem_tools(
        self, tmp_path: Path
    ) -> None:
        """allowed_write_paths only injected into filesystem tools."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = {
            "tools": [
                {"module": "tool-filesystem", "config": {}},
                {"module": "tool-other", "config": {}},
            ]
        }

        result = manager._inject_runtime_config(
            mount_plan=mount_plan,
            session_id="sess-123",
            project_path="/test/path",
        )

        # Filesystem tool should have allowed_write_paths
        assert "allowed_write_paths" in result["tools"][0]["config"]

        # Other tools should not
        assert "allowed_write_paths" not in result["tools"][1]["config"]

    def test_inject_api_key_to_providers(self, tmp_path: Path) -> None:
        """api_key is injected into all providers."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = {
            "providers": [
                {"module": "provider-anthropic", "config": {}},
            ]
        }

        result = manager._inject_runtime_config(
            mount_plan=mount_plan,
            session_id="sess-123",
            project_path="/test/path",
            api_key="sk-test-key",
        )

        assert result["providers"][0]["config"]["api_key"] == "sk-test-key"

    def test_no_api_key_when_not_provided(self, tmp_path: Path) -> None:
        """api_key is not injected when not provided."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = {
            "providers": [
                {"module": "provider-anthropic", "config": {}},
            ]
        }

        result = manager._inject_runtime_config(
            mount_plan=mount_plan,
            session_id="sess-123",
            project_path="/test/path",
        )

        assert "api_key" not in result["providers"][0]["config"]

    def test_creates_config_dict_if_missing(self, tmp_path: Path) -> None:
        """Creates config dict if tool/hook doesn't have one."""
        manager = LakehouseBundleManager(home_dir=tmp_path)
        mount_plan = {
            "tools": [
                {"module": "tool-test"},  # No config key
            ]
        }

        result = manager._inject_runtime_config(
            mount_plan=mount_plan,
            session_id="sess-123",
            project_path="/test/path",
        )

        assert "config" in result["tools"][0]
        assert result["tools"][0]["config"]["working_dir"] == "/test/path"


class TestRegistryBundles:
    """Tests for registry_bundles parameter."""

    def test_registry_bundles_registered_first(self, tmp_path: Path) -> None:
        """Registry bundles are registered before local discovery."""
        # Create a local bundle with same name as registry bundle
        bundles_dir = tmp_path / "share" / "bundles"
        bundles_dir.mkdir(parents=True)
        (bundles_dir / "my-bundle.md").write_text(
            "---\nbundle:\n  name: my-bundle\n  version: 1.0.0\n---\n"
        )

        # Pass registry_bundles that would conflict
        registry_bundles = {
            "my-bundle": "git+https://github.com/test/repo@main#bundle.md"
        }

        manager = LakehouseBundleManager(
            home_dir=tmp_path,
            registry_bundles=registry_bundles,
        )

        # The registry bundle should take precedence (local file skipped)
        # Check that my-bundle is in _bundle_info with source="registry"
        assert "my-bundle" in manager._bundle_info
        assert manager._bundle_info["my-bundle"].source == "registry"

    def test_local_bundles_discovered_when_not_in_registry(self, tmp_path: Path) -> None:
        """Local bundles are discovered if not in registry_bundles."""
        # Create a local bundle
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)
        (bundles_dir / "local-only.md").write_text(
            "---\nbundle:\n  name: local-only\n  version: 1.0.0\n---\n"
        )

        # Pass registry_bundles without local-only
        registry_bundles = {
            "remote-bundle": "git+https://github.com/test/repo@main#bundle.md"
        }

        manager = LakehouseBundleManager(
            home_dir=tmp_path,
            registry_bundles=registry_bundles,
        )

        # Local bundle should be discovered with source="user"
        assert "local-only" in manager._bundle_info
        assert manager._bundle_info["local-only"].source == "user"
        # Registry bundle should also be tracked with source="registry"
        assert "remote-bundle" in manager._bundle_info
        assert manager._bundle_info["remote-bundle"].source == "registry"

    def test_empty_registry_bundles_allows_local_discovery(self, tmp_path: Path) -> None:
        """Empty registry_bundles doesn't block local discovery."""
        # Create a local bundle
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)
        (bundles_dir / "test.md").write_text(
            "---\nbundle:\n  name: test\n  version: 1.0.0\n---\n"
        )

        manager = LakehouseBundleManager(
            home_dir=tmp_path,
            registry_bundles={},
        )

        assert "test" in manager.list_available_bundles()

    def test_none_registry_bundles_works(self, tmp_path: Path) -> None:
        """None registry_bundles is handled correctly."""
        # Create a local bundle
        bundles_dir = tmp_path / "bundles"
        bundles_dir.mkdir(parents=True)
        (bundles_dir / "test.md").write_text(
            "---\nbundle:\n  name: test\n  version: 1.0.0\n---\n"
        )

        manager = LakehouseBundleManager(
            home_dir=tmp_path,
            registry_bundles=None,
        )

        assert "test" in manager.list_available_bundles()
