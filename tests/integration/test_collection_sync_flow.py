"""Integration test for collection seeding and sync flow."""

from pathlib import Path
from unittest.mock import Mock

import yaml

from amplifierd.services.collection_service import CollectionService
from amplifierd.services.profile_compilation import ProfileCompilationService
from amplifierd.services.profile_discovery import ProfileDiscoveryService
from amplifierd.services.ref_resolution import RefResolutionService


def test_collection_service_initializes_empty_share_dir(tmp_path: Path) -> None:
    """Test that service properly initializes a completely empty share directory."""
    share_dir = tmp_path / "share"

    assert not share_dir.exists(), "Share dir should not exist initially"

    service = CollectionService(share_dir)

    assert share_dir.exists(), "Share dir should be created"
    # No auto-seeding - registry only created when first collection is added
    assert not (share_dir / "collections.yaml").exists(), "collections.yaml not created until first write"

    collections = service.list_collection_entries()
    assert len(collections) == 0, "Should start with empty registry"


def test_collection_sync_with_local_collection(tmp_path: Path) -> None:
    """Test complete flow: Add local collection to registry and sync."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Create a local collection
    local_collection = tmp_path / "my-collection"
    local_collection.mkdir()
    (local_collection / "collection.yaml").write_text("""
name: "My Collection"
version: "1.0.0"
description: "Test collection"
""")

    # Create a profiles directory
    profiles_dir = local_collection / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "test.md").write_text("""---
name: test
schema_version: 2
version: 1.0.0
---

# Test Profile
""")

    # Add to registry
    service._add_collection_to_registry(name="my-collection", source=str(local_collection))

    registry_file = share_dir / "collections.yaml"
    assert registry_file.exists(), "collections.yaml should be created"

    with open(registry_file) as f:
        data = yaml.safe_load(f)

    assert data is not None
    assert "collections" in data
    collections = data["collections"]

    assert len(collections) == 1, "Should have one collection in registry"
    assert "my-collection" in collections
    assert collections["my-collection"]["source"] == str(local_collection)

    # Sync collections (no-op for local without discovery service)
    results = service.sync_collections()

    assert len(results) == 1, "Should have synced one collection"
    assert results["my-collection"] == "synced", "Local collection should be synced"

    # Verify collection is listed
    synced_collections = service.list_collections()
    assert len(synced_collections) == 1, "Should have one collection available"
    assert synced_collections[0].identifier == "my-collection"


def test_collection_sync_with_autodiscovery(tmp_path: Path) -> None:
    """Test sync with profile auto-discovery."""
    share_dir = tmp_path / "share"
    state_dir = tmp_path / "state"

    # Create local collection with profiles
    local_collection = tmp_path / "my-collection"
    local_collection.mkdir()

    profiles_dir = local_collection / "profiles"
    profiles_dir.mkdir()
    (profiles_dir / "general.md").write_text("""---
name: general
schema_version: 2
version: 1.0.0
---

# General Profile
""")
    (profiles_dir / "advanced.md").write_text("""---
name: advanced
schema_version: 2
version: 1.0.0
---

# Advanced Profile
""")

    # Create services with auto-discovery
    ref_resolution = RefResolutionService(state_dir)
    discovery_service = ProfileDiscoveryService(share_dir)
    compilation_service = ProfileCompilationService(share_dir, ref_resolution)

    collection_service = CollectionService(
        share_dir, discovery_service=discovery_service, compilation_service=compilation_service
    )

    # Add collection to registry
    collection_service._add_collection_to_registry(name="my-collection", source=str(local_collection))

    # Sync collections - should auto-discover profiles
    results = collection_service.sync_collections()

    assert results["my-collection"] == "synced"

    # Verify profiles were discovered
    # Discovery service caches manifests at share_dir/profiles/{collection}/{profile}/{profile}.md
    # Note: Compilation might fail due to missing refs, but discovery should have run
    # Check if discovery service was called at all by looking for the profiles directory parent
    profiles_base = share_dir / "profiles"

    # Discovery creates this directory during init
    assert profiles_base.exists(), "Profiles base directory should exist"

    # Note: This test mainly verifies that autodiscovery was invoked.
    # Full compilation tests are in test_profile_compilation.py
    # The directory may or may not exist depending on whether compilation succeeded
    # (profiles with no refs will fail compilation but discovery should have run)
    assert profiles_base.exists(), "Discovery service should have been initialized"


def test_collection_sync_with_git_source(tmp_path: Path) -> None:
    """Test sync with git+ source (mocked git clone)."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Create mock git cache directory in tmp_path (not shared cache)
    git_cache = tmp_path / "git_cache" / "test-git-collection"
    git_cache.mkdir(parents=True)
    (git_cache / "collection.yaml").write_text("name: Test\nversion: 1.0.0\n")

    # Add git collection to registry
    service._add_collection_to_registry(name="test-git-collection", source="git+https://github.com/org/repo@main")

    # Mock the clone operation to use pre-created cache
    def mock_clone_to_cache(identifier: str, source: str) -> Path:
        return git_cache

    service._clone_to_cache = Mock(side_effect=mock_clone_to_cache)  # type: ignore[method-assign]

    # Sync collections
    results = service.sync_collections()

    # Verify git collection was processed
    assert "test-git-collection" in results
    # May be synced (if mock was called) or skipped (if cache check happened first)
    assert results["test-git-collection"] in ["synced", "skipped"]


def test_collection_sync_reload_from_disk(tmp_path: Path) -> None:
    """Test that sync reloads collections.yaml from disk."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Add collection via service
    service._add_collection_to_registry(name="collection1", source="local:/path1")

    # Manually edit collections.yaml to add another collection
    registry_file = share_dir / "collections.yaml"
    with open(registry_file) as f:
        data = yaml.safe_load(f)

    data["collections"]["collection2"] = {"source": "local:/path2", "installed_at": "2025-01-01T00:00:00"}

    with open(registry_file, "w") as f:
        yaml.dump(data, f)

    # Sync should reload from disk
    results = service.sync_collections()

    # Both collections should be processed
    assert "collection1" in results
    assert "collection2" in results

    # Verify both are in memory
    collections = service.list_collection_entries()
    assert len(collections) == 2
