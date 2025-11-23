"""Tests for bundled: collection mechanism."""

from pathlib import Path

import pytest

from amplifierd.services.simple_collection_service import SimpleCollectionService


class TestBundledCollectionResolution:
    """Test bundled: source resolution."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> SimpleCollectionService:
        """Create collection service for testing."""
        return SimpleCollectionService(share_dir=tmp_path)

    def test_resolve_bundled_foundation(self, service: SimpleCollectionService) -> None:
        """Test resolving actual bundled foundation collection."""
        path = service._resolve_bundled_source("bundled:amplifierd.data.collections.foundation")

        assert path.exists()
        assert path.is_dir()
        assert any(path.iterdir())

    def test_resolve_bundled_developer_expertise(self, service: SimpleCollectionService) -> None:
        """Test resolving developer expertise collection."""
        path = service._resolve_bundled_source("bundled:amplifierd.data.collections.developer-expertise")

        assert path.exists()
        assert path.is_dir()

    def test_bundled_has_expected_structure(self, service: SimpleCollectionService) -> None:
        """Test that resolved bundled collection has expected directory structure."""
        path = service._resolve_bundled_source("bundled:amplifierd.data.collections.foundation")

        has_resources = any((path / subdir).is_dir() for subdir in ["modules", "profiles", "agents", "context"])
        assert has_resources, "Bundled collection should have at least one resource directory"

    def test_bundled_invalid_format_single_part(self, service: SimpleCollectionService) -> None:
        """Test error on invalid bundled: format (single part)."""
        with pytest.raises(ValueError, match="Invalid bundled source format"):
            service._resolve_bundled_source("bundled:single")

    def test_bundled_missing_module(self, service: SimpleCollectionService) -> None:
        """Test error on missing module."""
        with pytest.raises(ValueError, match="Module not found|Cannot resolve"):
            service._resolve_bundled_source("bundled:nonexistent.package.collection")

    def test_bundled_missing_resource(self, service: SimpleCollectionService) -> None:
        """Test error on missing resource within valid package."""
        with pytest.raises(FileNotFoundError, match="not found"):
            service._resolve_bundled_source("bundled:amplifierd.data.collections.nonexistent")

    def test_bundled_not_a_directory(self, service: SimpleCollectionService) -> None:
        """Test error when bundled resource is not a directory."""
        with pytest.raises((ValueError, FileNotFoundError)):
            service._resolve_bundled_source("bundled:amplifierd.__init__")


class TestCloneToCacheBundled:
    """Test _clone_to_cache with bundled sources."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> SimpleCollectionService:
        """Create collection service for testing."""
        return SimpleCollectionService(share_dir=tmp_path)

    def test_clone_to_cache_bundled_foundation(self, service: SimpleCollectionService) -> None:
        """Test _clone_to_cache with bundled source."""
        path = service._clone_to_cache(identifier="foundation", source="bundled:amplifierd.data.collections.foundation")

        assert path.exists()
        assert path.is_dir()
        assert "amplifierd" in str(path)
        assert "data/collections" in str(path)

    def test_clone_to_cache_bundled_no_caching(self, service: SimpleCollectionService) -> None:
        """Test that bundled sources don't use cache directory."""
        path1 = service._clone_to_cache("foundation", "bundled:amplifierd.data.collections.foundation")
        path2 = service._clone_to_cache("foundation", "bundled:amplifierd.data.collections.foundation")

        assert path1 == path2
        assert "state/collections" not in str(path1)

    def test_clone_to_cache_bundled_vs_local(self, service: SimpleCollectionService, tmp_path: Path) -> None:
        """Test that bundled and local sources are handled differently."""
        local_coll = tmp_path / "local_collection"
        local_coll.mkdir()
        (local_coll / "profiles").mkdir()

        bundled_path = service._clone_to_cache("foundation", "bundled:amplifierd.data.collections.foundation")
        local_path = service._clone_to_cache("local-test", f"local:{local_coll}")

        assert "amplifierd" in str(bundled_path)
        assert str(local_coll) == str(local_path)
        assert bundled_path != local_path


class TestBundledCollectionTypes:
    """Test collection type detection for bundled sources."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> SimpleCollectionService:
        """Create collection service for testing."""
        return SimpleCollectionService(share_dir=tmp_path)

    def test_list_collections_shows_bundled_type(self, service: SimpleCollectionService) -> None:
        """Test that bundled collections are correctly typed in list."""
        collections = service.list_collections()

        bundled_collections = [c for c in collections if c.type == "bundled"]
        assert len(bundled_collections) > 0, "Should have at least one bundled collection"

        for coll in bundled_collections:
            assert coll.source.startswith("bundled:"), "Bundled collections should have bundled: source"
            assert coll.package_bundled is True, "Bundled collections should be marked as package_bundled"

    def test_get_collection_shows_bundled_type(self, service: SimpleCollectionService) -> None:
        """Test that bundled collection details show correct type."""
        collections = service.list_collections()
        bundled_collections = [c for c in collections if c.type == "bundled"]

        if not bundled_collections:
            pytest.skip("No bundled collections available")

        identifier = bundled_collections[0].identifier
        details = service.get_collection(identifier)

        assert details.type == "bundled"
        assert details.source.startswith("bundled:")
        assert details.package_bundled is True


class TestBundledErrorHandling:
    """Test error handling for bundled collections."""

    @pytest.fixture
    def service(self, tmp_path: Path) -> SimpleCollectionService:
        """Create collection service for testing."""
        return SimpleCollectionService(share_dir=tmp_path)

    def test_bundled_error_message_clarity(self, service: SimpleCollectionService) -> None:
        """Test that error messages for bundled collections are clear and helpful."""
        try:
            service._resolve_bundled_source("bundled:nonexistent.package.collection")
            pytest.fail("Should have raised ValueError")
        except ValueError as e:
            error_msg = str(e)
            assert "Cannot resolve" in error_msg or "Module not found" in error_msg
            assert "bundled" in error_msg.lower()

    def test_bundled_not_found_provides_path(self, service: SimpleCollectionService) -> None:
        """Test that FileNotFoundError includes resolved path for debugging."""
        try:
            service._resolve_bundled_source("bundled:amplifierd.data.collections.missing")
            pytest.fail("Should have raised FileNotFoundError")
        except FileNotFoundError as e:
            error_msg = str(e)
            assert "not found" in error_msg.lower()
            assert "amplifierd.data.collections.missing" in error_msg
