#!/usr/bin/env python3
"""Manual test to demonstrate collection seeding behavior."""

import tempfile
from pathlib import Path

import yaml

from amplifierd.services.simple_collection_service import SimpleCollectionService


def main() -> None:
    """Demonstrate collection seeding and sync."""
    with tempfile.TemporaryDirectory() as tmpdir:
        share_dir = Path(tmpdir) / "share"

        print(f"\n{'=' * 60}")
        print("Testing Collection Seeding and Sync Flow")
        print(f"{'=' * 60}\n")

        print("Step 1: Initialize SimpleCollectionService")
        print(f"  Share directory: {share_dir}")

        service = SimpleCollectionService(share_dir)

        print("  ✓ Service initialized\n")

        print("Step 2: Check collections.yaml was seeded")
        registry_file = share_dir / "collections.yaml"
        print(f"  Registry file: {registry_file}")
        print(f"  Exists: {registry_file.exists()}")

        with open(registry_file) as f:
            data = yaml.safe_load(f)

        print(f"\n  Collections in registry: {len(data['collections'])}")
        for name, entry in data["collections"].items():
            print(f"    - {name}:")
            print(f"        source: {entry['source']}")
            print(f"        package_bundled: {entry['package_bundled']}")
            print(f"        version: {entry['version']}")

        print("\nStep 3: Sync collections (mount from package)")

        results = service.sync_collections()

        print(f"  Sync results: {results}")

        print("\nStep 4: List mounted collections")
        collections = service.list_collections()
        print(f"  Found {len(collections)} collection(s):")

        for collection in collections:
            print(f"\n    - {collection.identifier}:")
            print(f"        type: {collection.type}")
            print(f"        source: {collection.source}")
            print(f"        package_bundled: {collection.package_bundled}")

            details = service.get_collection(collection.identifier)
            print(f"        modules: {len(details.modules.providers)} provider(s)")
            print(f"        profiles: {len(details.profiles)} profile(s)")
            print(f"        agents: {len(details.agents)} agent(s)")

        print("\nStep 5: Verify resources extracted to share directory")
        for collection in collections:
            print(f"\n  Resources for '{collection.identifier}':")
            for resource_type in ["modules", "profiles", "agents", "context"]:
                resource_dir = share_dir / resource_type / collection.identifier
                if resource_dir.exists():
                    count = len(list(resource_dir.rglob("*")))
                    print(f"    {resource_type}: {count} file(s)")

        print(f"\n{'=' * 60}")
        print("Test completed successfully!")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
