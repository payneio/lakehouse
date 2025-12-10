"""Metadata initialization service.

Initializes metadata store from collections.yaml on first run or when metadata is missing.
"""

import logging
from datetime import UTC
from datetime import datetime
from pathlib import Path

import yaml
from amplifier_library.storage import get_share_dir
from amplifier_library.storage.paths import get_profiles_dir

from amplifierd.models.metadata import CollectionMetadata
from amplifierd.models.metadata import ProfileMetadata
from amplifierd.services.metadata_store import MetadataStore

logger = logging.getLogger(__name__)


def initialize_metadata_from_registry(metadata_store: MetadataStore) -> None:
    """Initialize metadata store from collections.yaml on first run.

    For each collection in registry:
    - Create CollectionMetadata entry
    - Discover profiles
    - Create ProfileMetadata entries

    Args:
        metadata_store: Metadata store to populate

    Raises:
        FileNotFoundError: If collections.yaml not found
        ValueError: If collections.yaml is invalid
    """
    share_dir = get_share_dir()
    registry_file = share_dir / "collections.yaml"

    if not registry_file.exists():
        logger.warning(f"Registry file not found: {registry_file}")
        return

    logger.info(f"Initializing metadata from registry: {registry_file}")

    try:
        with registry_file.open() as f:
            registry_data = yaml.safe_load(f)

        if not registry_data or "collections" not in registry_data:
            logger.warning("No collections found in registry")
            return

        collections = registry_data["collections"]
        logger.info(f"Found {len(collections)} collection(s) in registry")

        profiles_dir = get_profiles_dir()
        now = datetime.now(UTC)

        for collection_id, collection_config in collections.items():
            try:
                _initialize_collection(
                    metadata_store=metadata_store,
                    collection_id=collection_id,
                    collection_config=collection_config,
                    profiles_dir=profiles_dir,
                    now=now,
                )
            except Exception as e:
                logger.error(f"Failed to initialize collection {collection_id}: {e}", exc_info=True)
                # Continue with other collections

        logger.info("Metadata initialization complete")

    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in registry file: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to initialize metadata: {e}") from e


def _initialize_collection(
    metadata_store: MetadataStore,
    collection_id: str,
    collection_config: dict,
    profiles_dir: Path,
    now: datetime,
) -> None:
    """Initialize metadata for a single collection.

    Args:
        metadata_store: Metadata store
        collection_id: Collection identifier
        collection_config: Collection configuration from registry
        profiles_dir: Root profiles directory
        now: Current timestamp
    """
    logger.info(f"Initializing collection: {collection_id}")

    # Determine source type and location
    source_location = collection_config.get("source", "")
    source_type = "git" if source_location.startswith("git@") or source_location.startswith("https://") else "local"

    # Mount path is where the collection is cached
    mount_path = profiles_dir / collection_id

    # Create collection metadata
    collection_metadata = CollectionMetadata(
        collection_id=collection_id,
        source_type=source_type,
        source_location=source_location,
        mount_path=mount_path,
        installed_at=now,
        last_updated=now,
        last_checked=now,
    )

    # Save collection
    metadata_store.save_collection(collection_metadata)
    logger.debug(f"Created collection metadata: {collection_id}")

    # Discover and initialize profiles
    collection_dir = profiles_dir / collection_id
    if not collection_dir.exists():
        logger.warning(f"Collection directory not found: {collection_dir}")
        return

    profile_count = 0
    for profile_dir in collection_dir.iterdir():
        if not profile_dir.is_dir():
            continue

        manifest_file = profile_dir / "manifest.yaml"
        if not manifest_file.exists():
            continue

        try:
            profile_name = profile_dir.name
            profile_id = f"{collection_id}/{profile_name}"

            # Get manifest file modification time
            manifest_modified = datetime.fromtimestamp(manifest_file.stat().st_mtime, UTC)

            # Compute manifest hash
            import hashlib

            manifest_content = manifest_file.read_bytes()
            manifest_hash = hashlib.sha256(manifest_content).hexdigest()

            # Create profile metadata
            profile_metadata = ProfileMetadata(
                profile_id=profile_id,
                collection_id=collection_id,
                source_path=profile_dir,
                cache_path=None,  # Will be set when profile is compiled
                source_modified=manifest_modified,
                cache_built=None,  # Not compiled yet
                manifest_hash=manifest_hash,
                last_checked=None,  # Not checked yet
            )

            metadata_store.save_profile(profile_metadata)
            profile_count += 1
            logger.debug(f"Created profile metadata: {profile_id}")

        except Exception as e:
            logger.error(f"Failed to initialize profile {profile_dir.name}: {e}", exc_info=True)
            continue

    logger.info(f"Initialized {profile_count} profile(s) for collection {collection_id}")


def should_initialize_metadata(metadata_store: MetadataStore) -> bool:
    """Check if metadata store needs initialization.

    Args:
        metadata_store: Metadata store to check

    Returns:
        True if metadata store is empty or incomplete
    """
    collections = metadata_store.list_collections()
    return len(collections) == 0
