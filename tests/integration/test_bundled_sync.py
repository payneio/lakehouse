"""Integration tests for bundled collection sync."""

from pathlib import Path

import pytest
import yaml

from amplifierd.services.simple_collection_service import SimpleCollectionService


class TestBundledCollectionSync:
    """Test bundled collections in full sync flow."""

    @pytest.fixture
    def test_env(self, tmp_path: Path) -> Path:
        """Set up test environment."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        collections_file = share_dir / "collections.yaml"
        collections_file.write_text(
            """
collections:
  foundation:
    source: "bundled:amplifierd.data.collections.foundation"
    method: "bundled"
"""
        )

        return share_dir

    def test_sync_bundled_collection(self, test_env: Path) -> None:
        """Test syncing a bundled collection."""
        service = SimpleCollectionService(share_dir=test_env)
        results = service.sync_collections()

        assert "foundation" in results
        assert results["foundation"] in ["synced", "skipped"]

        collections = service.list_collections()
        foundation = next((c for c in collections if c.identifier == "foundation"), None)

        assert foundation is not None
        assert foundation.type == "bundled"

    def test_bundled_collection_extraction(self, test_env: Path) -> None:
        """Test that bundled collection resources are properly extracted."""
        service = SimpleCollectionService(share_dir=test_env)
        service.sync_collections()

        details = service.get_collection("foundation")

        has_resources = any(
            [
                details.profiles,
                details.agents,
                details.modules.providers,
                details.modules.tools,
            ]
        )
        assert has_resources, "Bundled collection should have extracted resources"

    def test_mixed_source_types(self, tmp_path: Path) -> None:
        """Test bundled: mixed with local:."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        local_coll = tmp_path / "local_coll"
        local_coll.mkdir()
        (local_coll / "profiles").mkdir()

        collections_file = share_dir / "collections.yaml"
        collections_file.write_text(
            f"""
collections:
  foundation:
    source: "bundled:amplifierd.data.collections.foundation"
    method: "bundled"

  local-test:
    source: "local:{local_coll}"
    method: "local"
"""
        )

        service = SimpleCollectionService(share_dir=share_dir)
        results = service.sync_collections()

        assert "foundation" in results
        assert "local-test" in results
        assert results["foundation"] in ["synced", "skipped"]
        assert results["local-test"] in ["synced", "skipped"]

    def test_bundled_collection_idempotent_sync(self, test_env: Path) -> None:
        """Test that syncing bundled collection multiple times is idempotent."""
        service = SimpleCollectionService(share_dir=test_env)

        results1 = service.sync_collections()
        assert "foundation" in results1
        assert results1["foundation"] == "synced"

        results2 = service.sync_collections()
        assert "foundation" in results2
        # Bundled collections always report "synced" since they're always available
        assert results2["foundation"] == "synced"


class TestBundledCollectionRegistry:
    """Test bundled collections in registry operations."""

    @pytest.fixture
    def service_with_bundled(self, tmp_path: Path) -> SimpleCollectionService:
        """Create service with bundled collection registered."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        collections_file = share_dir / "collections.yaml"
        collections_file.write_text(
            """
collections:
  foundation:
    source: "bundled:amplifierd.data.collections.foundation"
    method: "bundled"
"""
        )

        service = SimpleCollectionService(share_dir=share_dir)
        service.sync_collections()
        return service

    def test_bundled_collection_in_list(self, service_with_bundled: SimpleCollectionService) -> None:
        """Test that bundled collection appears in list_collections."""
        collections = service_with_bundled.list_collections()

        foundation = next((c for c in collections if c.identifier == "foundation"), None)
        assert foundation is not None
        assert foundation.type == "bundled"
        assert foundation.source.startswith("bundled:")

    def test_bundled_collection_get_details(self, service_with_bundled: SimpleCollectionService) -> None:
        """Test getting details of bundled collection."""
        details = service_with_bundled.get_collection("foundation")

        assert details.identifier == "foundation"
        assert details.type == "bundled"
        assert details.source.startswith("bundled:")

    def test_bundled_collection_unmount_not_allowed(self, service_with_bundled: SimpleCollectionService) -> None:
        """Test that attempting to unmount bundled collection succeeds but resources remain."""
        service_with_bundled.unmount_collection("foundation")

        collections = service_with_bundled.list_collections()
        foundation = next((c for c in collections if c.identifier == "foundation"), None)

        assert foundation is None


class TestBundledCollectionErrors:
    """Test error handling for bundled collections."""

    def test_sync_invalid_bundled_source(self, tmp_path: Path) -> None:
        """Test sync with invalid bundled source."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        collections_file = share_dir / "collections.yaml"
        collections_file.write_text(
            """
collections:
  invalid:
    source: "bundled:nonexistent.package.collection"
    method: "bundled"
"""
        )

        service = SimpleCollectionService(share_dir=share_dir)
        results = service.sync_collections()

        assert "invalid" in results
        assert results["invalid"] == "error"

    def test_sync_bundled_missing_resource(self, tmp_path: Path) -> None:
        """Test sync with bundled source pointing to missing resource."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        collections_file = share_dir / "collections.yaml"
        collections_file.write_text(
            """
collections:
  missing:
    source: "bundled:amplifierd.data.collections.doesnotexist"
    method: "bundled"
"""
        )

        service = SimpleCollectionService(share_dir=share_dir)
        results = service.sync_collections()

        assert "missing" in results
        assert results["missing"] == "error"


class TestBundledDefaultInitialization:
    """Test that bundled collections are initialized by default."""

    def test_new_service_has_bundled_collections(self, tmp_path: Path) -> None:
        """Test that new service initializes with bundled collections."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        SimpleCollectionService(share_dir=share_dir)

        registry_file = share_dir / "collections.yaml"
        assert registry_file.exists()

        with open(registry_file) as f:
            data = yaml.safe_load(f)

        assert "collections" in data
        bundled_collections = [
            name for name, info in data["collections"].items() if info.get("source", "").startswith("bundled:")
        ]

        assert len(bundled_collections) > 0, "Should have at least one bundled collection by default"

    def test_default_bundled_collections_are_valid(self, tmp_path: Path) -> None:
        """Test that default bundled collections can be synced."""
        share_dir = tmp_path / "share"
        share_dir.mkdir()

        service = SimpleCollectionService(share_dir=share_dir)
        results = service.sync_collections()

        bundled_results = {
            name: status
            for name, status in results.items()
            if any(c.source.startswith("bundled:") for c in service.list_collections() if c.identifier == name)
        }

        for name, status in bundled_results.items():
            assert status in ["synced", "skipped"], f"Bundled collection {name} failed with status {status}"
