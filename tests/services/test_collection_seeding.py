"""Test collection registry functionality."""

from pathlib import Path

from amplifierd.services.collection_service import CollectionService


def test_empty_registry_on_init(tmp_path: Path) -> None:
    """Test that new service starts with empty registry."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Registry should be empty on first init (no default seeding)
    collections = service.list_collection_entries()
    assert len(collections) == 0, "New service should have empty registry"

    registry_file = share_dir / "collections.yaml"
    assert not registry_file.exists(), "Empty registry should not create file yet"


def test_registry_persistence(tmp_path: Path) -> None:
    """Test that registry changes are persisted across service instances."""
    share_dir = tmp_path / "share"

    # First service adds a collection
    service1 = CollectionService(share_dir)
    service1._add_collection_to_registry(name="test-collection", source="git+https://github.com/org/repo@main")

    # Registry file should exist
    assert (share_dir / "collections.yaml").exists()

    # Second service should load the persisted collection
    service2 = CollectionService(share_dir)
    collections = service2.list_collection_entries()
    assert len(collections) == 1, "Should load persisted collection"
    assert collections[0][0] == "test-collection"
    assert collections[0][1].source == "git+https://github.com/org/repo@main"


def test_mount_collection_adds_to_registry(tmp_path: Path) -> None:
    """Test that mounting a collection adds it to the registry."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Create a local collection
    local_collection = tmp_path / "local-collection"
    local_collection.mkdir()
    (local_collection / "collection.yaml").write_text("name: Test\nversion: 1.0.0\n")

    # Mount the collection
    service.mount_collection("local-test", str(local_collection))

    # Verify it's in the registry
    collections = service.list_collection_entries()
    assert len(collections) == 1
    assert collections[0][0] == "local-test"

    # Verify persistence
    service2 = CollectionService(share_dir)
    collections2 = service2.list_collection_entries()
    assert len(collections2) == 1
    assert collections2[0][0] == "local-test"


def test_unmount_collection_removes_from_registry(tmp_path: Path) -> None:
    """Test that unmounting removes collection from registry."""
    share_dir = tmp_path / "share"
    service = CollectionService(share_dir)

    # Add a collection
    service._add_collection_to_registry(name="test-collection", source="git+https://github.com/org/repo@main")

    # Verify it exists
    assert len(service.list_collection_entries()) == 1

    # Unmount it
    service.unmount_collection("test-collection")

    # Verify it's gone
    assert len(service.list_collection_entries()) == 0

    # Verify persistence
    service2 = CollectionService(share_dir)
    assert len(service2.list_collection_entries()) == 0
