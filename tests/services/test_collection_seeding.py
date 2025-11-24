"""Test collection registry seeding functionality."""

from pathlib import Path

import yaml

from amplifierd.services.collection_registry import CollectionRegistry


def test_initialize_with_defaults_creates_registry(tmp_path: Path) -> None:
    """Test that initialize_with_defaults creates minimal declarative collections.yaml."""
    share_dir = tmp_path / "share"
    registry = CollectionRegistry(share_dir)

    registry.initialize_with_defaults()

    registry_file = share_dir / "collections.yaml"
    assert registry_file.exists(), "collections.yaml should be created"

    # Load raw YAML to verify minimal format
    with open(registry_file) as f:
        data = yaml.safe_load(f)

    assert "collections" in data
    collections = data["collections"]
    assert len(collections) > 0, "Should have at least one package collection"

    # Verify minimal format (just source field)
    for name, entry in collections.items():
        assert "source" in entry, f"Collection {name} should have source field"
        assert entry["source"].startswith("bundled:"), f"Collection {name} should have bundled: source"
        # Minimal entries should NOT have full registry fields yet
        # Those are populated during sync


def test_initialize_with_defaults_skips_if_not_empty(tmp_path: Path) -> None:
    """Test that initialize_with_defaults skips if registry already has collections."""
    share_dir = tmp_path / "share"
    registry = CollectionRegistry(share_dir)

    registry.initialize_with_defaults()

    initial_collections = registry.load()
    initial_count = len(initial_collections)

    registry.initialize_with_defaults()

    final_collections = registry.load()
    assert len(final_collections) == initial_count, "Should not add more collections on second init"


def test_package_collections_have_expected_structure() -> None:
    """Test that package collections directory structure exists."""
    package_dir = Path(__file__).parent.parent.parent / "amplifierd"
    collections_dir = package_dir / "data" / "collections"

    assert collections_dir.exists(), "Package collections directory should exist"

    found_collections = []
    for dir_path in collections_dir.iterdir():
        if dir_path.is_dir() and not dir_path.name.startswith((".", "_")):
            has_resources = any((dir_path / subdir).is_dir() for subdir in ["modules", "profiles", "agents", "context"])
            if has_resources:
                found_collections.append(dir_path.name)

    assert len(found_collections) > 0, "Should have at least one valid package collection"
    assert "foundation" in found_collections or "developer-expertise" in found_collections
