"""Tests for bundle source content retrieval."""

from pathlib import Path

import pytest
from lakehouse_library.bundles import LakehouseBundleManager


class TestBundleSourceContent:
    """Tests for get_bundle_source_content method."""

    @pytest.mark.asyncio
    async def test_get_source_for_local_bundle(self, tmp_path: Path) -> None:
        """Can retrieve source content for local bundles."""
        bundles_dir = tmp_path / "share" / "bundles"
        bundles_dir.mkdir(parents=True)

        # Create a local bundle
        bundle_content = """---
bundle:
  name: local-bundle
  version: 1.0.0
---
# Local Bundle

Test content.
"""
        (bundles_dir / "local-bundle.md").write_text(bundle_content)

        manager = LakehouseBundleManager(home_dir=tmp_path)
        content, path, file_format = await manager.get_bundle_source_content("local-bundle")

        assert content == bundle_content
        assert "local-bundle.md" in path
        assert file_format == "md"

    @pytest.mark.asyncio
    async def test_get_source_for_directory_bundle(self, tmp_path: Path) -> None:
        """Can retrieve source content for directory-based bundles."""
        bundles_dir = tmp_path / "share" / "bundles"
        bundle_dir = bundles_dir / "test-bundle"
        bundle_dir.mkdir(parents=True)

        bundle_content = """---
bundle:
  name: test-bundle
  version: 1.0.0
---
# Test Bundle
"""
        (bundle_dir / "bundle.md").write_text(bundle_content)

        manager = LakehouseBundleManager(home_dir=tmp_path)
        content, path, file_format = await manager.get_bundle_source_content("test-bundle")

        assert content == bundle_content
        assert "bundle.md" in path
        assert file_format == "md"

    @pytest.mark.asyncio
    async def test_error_for_nonexistent_bundle(self, tmp_path: Path) -> None:
        """Raises ValueError for bundles that don't exist."""
        manager = LakehouseBundleManager(home_dir=tmp_path)

        with pytest.raises(ValueError, match="Bundle not found"):
            await manager.get_bundle_source_content("nonexistent")
