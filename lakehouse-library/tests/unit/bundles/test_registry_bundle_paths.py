"""Test to understand base_path behavior for registry bundles."""

from pathlib import Path

import pytest
from lakehouse_library.bundles import LakehouseBundleManager


class TestRegistryBundlePaths:
    """Debug tests for understanding registry bundle path resolution."""

    @pytest.mark.asyncio
    async def test_base_path_for_subdirectory_fragment(self, tmp_path: Path) -> None:
        """Test what base_path contains for subdirectory= fragments."""
        # Create a mock registry bundle structure
        cache_dir = tmp_path / "cache" / "test-repo-hash"
        bundles_subdir = cache_dir / "bundles"
        bundles_subdir.mkdir(parents=True)

        # Create bundle file
        bundle_content = """---
bundle:
  name: test-bundle
  version: 1.0.0
---
# Test
"""
        (bundles_subdir / "test-bundle.md").write_text(bundle_content)

        # Create cache meta file (Foundation looks for this)
        (cache_dir / ".amplifier_cache_meta.json").write_text('{"cached_at": "2026-01-24T00:00:00"}')

        # Register with subdirectory fragment
        registry_bundles = {"test-bundle": f"git+file://{cache_dir}@main#subdirectory=bundles/test-bundle.md"}

        manager = LakehouseBundleManager(home_dir=tmp_path, registry_bundles=registry_bundles)

        # Load the bundle to see what base_path is set to
        bundle = await manager._registry._load_single(
            "test-bundle",
            auto_register=False,
            auto_include=False,
        )

        print(f"\nBundle name: {bundle.name}")
        print(f"base_path: {bundle.base_path}")
        print(f"base_path exists: {bundle.base_path.exists() if bundle.base_path else 'None'}")
        print(f"base_path is_dir: {bundle.base_path.is_dir() if bundle.base_path else 'None'}")

        # What files are in base_path?
        if bundle.base_path and bundle.base_path.exists():
            print(f"Contents of base_path:")
            for item in bundle.base_path.iterdir():
                print(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")

        # Now test source content retrieval
        try:
            content, path, fmt = await manager.get_bundle_source_content("test-bundle")
            print(f"\nSource retrieval SUCCESS")
            print(f"Path: {path}")
            print(f"Format: {fmt}")
            assert content == bundle_content
        except Exception as e:
            print(f"\nSource retrieval FAILED: {e}")
            raise
