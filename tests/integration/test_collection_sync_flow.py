"""Integration test for collection seeding and sync flow."""

from pathlib import Path

import yaml

from amplifierd.services.simple_collection_service import SimpleCollectionService


def test_collection_sync_seeds_and_mounts_package_collections(tmp_path: Path) -> None:
    """Test complete flow: seeding collections.yaml and syncing package collections."""
    share_dir = tmp_path / "share"
    service = SimpleCollectionService(share_dir)

    registry_file = share_dir / "collections.yaml"
    assert registry_file.exists(), "collections.yaml should be created on service init"

    with open(registry_file) as f:
        data = yaml.safe_load(f)

    assert data is not None
    assert "collections" in data
    collections = data["collections"]

    assert len(collections) > 0, "Should have seeded package collections"

    for name, entry in collections.items():
        assert entry["source"].startswith("bundled:"), f"Collection {name} should have bundled: source"

    results = service.sync_collections()

    assert len(results) > 0, "Should have synced collections"

    for name, status in results.items():
        assert status in ["synced", "updated", "skipped"], f"Collection {name} should have valid status, got {status}"

    synced_collections = service.list_collections()
    assert len(synced_collections) > 0, "Should have mounted collections available"

    for collection in synced_collections:
        if collection.package_bundled:
            assert collection.identifier in collections, (
                f"Package collection {collection.identifier} should be in registry"
            )

            modules_dir = share_dir / "modules" / collection.identifier
            profiles_dir = share_dir / "profiles" / collection.identifier
            agents_dir = share_dir / "agents" / collection.identifier
            context_dir = share_dir / "context" / collection.identifier

            resource_dirs = [modules_dir, profiles_dir, agents_dir, context_dir]
            has_resources = any(d.exists() and any(d.iterdir()) for d in resource_dirs)

            assert has_resources, f"Collection {collection.identifier} should have extracted resources"


def test_collection_service_initializes_empty_share_dir(tmp_path: Path) -> None:
    """Test that service properly initializes a completely empty share directory."""
    share_dir = tmp_path / "share"

    assert not share_dir.exists(), "Share dir should not exist initially"

    service = SimpleCollectionService(share_dir)

    assert share_dir.exists(), "Share dir should be created"
    assert (share_dir / "collections.yaml").exists(), "collections.yaml should be created"

    collections = service.registry.load()
    assert len(collections) > 0, "Should have default collections"


def test_package_collection_source_format_resolved(tmp_path: Path) -> None:
    """Test that bundled: source format is correctly resolved during sync."""
    share_dir = tmp_path / "share"
    service = SimpleCollectionService(share_dir)

    results = service.sync_collections()

    for name, status in results.items():
        if status == "error":
            continue

        entry = service.registry.get_collection(name)
        if entry and entry.package_bundled:
            assert entry.source.startswith("bundled:"), f"Source for {name} should be bundled: format"
