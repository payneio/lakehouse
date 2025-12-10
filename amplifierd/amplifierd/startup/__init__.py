"""Startup handlers for amplifierd daemon.

Handles cache updates and initialization on daemon startup based on configuration.
"""

import logging
from datetime import UTC

from amplifierd.config.models import StartupConfig
from amplifierd.dependencies import get_status_service
from amplifierd.dependencies import get_update_service

logger = logging.getLogger(__name__)


async def handle_startup_updates(config: StartupConfig) -> None:
    """Handle cache updates on startup based on configuration.

    Bootstrap process:
    1. Read collections from collections.yaml
    2. Initialize metadata for any collections not in metadata store
    3. Check cache status (will now find missing collections)
    4. Update based on config.update_stale_caches

    Behavior based on configuration:
    - If check_cache_on_startup is False: Skip entirely
    - If check_cache_on_startup is True and update_stale_caches is False:
      Check cache status and log if outdated
    - If both are True: Check and update stale caches

    Args:
        config: Startup configuration
    """
    if not config.check_cache_on_startup:
        logger.info("Cache checking on startup disabled")
        return

    logger.info("Checking cache status on startup...")

    try:
        # STEP 1: Bootstrap metadata from collections.yaml
        from datetime import datetime

        from amplifier_library.cache.models import CollectionMetadata
        from amplifier_library.storage.paths import get_profiles_dir

        from amplifierd.dependencies import get_collection_service
        from amplifierd.dependencies import get_metadata_store

        collection_service = get_collection_service()
        metadata_store = get_metadata_store()

        # Get collections from YAML (source of truth)
        collections_from_yaml = collection_service.list_collection_entries()

        # Ensure metadata exists for each collection
        bootstrapped_count = 0
        profiles_dir = get_profiles_dir()

        for collection_id, entry in collections_from_yaml:
            existing_meta = metadata_store.get_collection(collection_id)
            if not existing_meta:
                # Create initial metadata for this collection
                logger.info(f"Bootstrapping metadata for collection: {collection_id}")

                # Determine source type from entry
                source_type = "git" if entry.source.startswith(("git@", "https://", "git+")) else "local"

                # Mount path is where collection will be cached
                mount_path = profiles_dir / collection_id

                metadata_store.save_collection(
                    CollectionMetadata(
                        collection_id=collection_id,
                        source_type=source_type,
                        source_location=entry.source,
                        mount_path=mount_path,
                        installed_at=datetime.min.replace(tzinfo=UTC),  # Never installed
                        last_checked=datetime.min.replace(tzinfo=UTC),  # Never checked
                        last_updated=None,  # Never updated
                        source_commit=None,  # No commit yet
                    )
                )
                bootstrapped_count += 1

        if bootstrapped_count > 0:
            logger.info(f"Bootstrapped metadata for {bootstrapped_count} collection(s)")

        # STEP 2: Now check status (will find bootstrapped collections as "missing")
        status_service = get_status_service()
        all_status = status_service.get_all_status()

        # Log overall status
        logger.info(f"Cache status: {all_status.overall_status}")

        if all_status.overall_status == "fresh":
            logger.info("All caches are fresh")
            return

        # Count stale/missing collections and profiles
        stale_collections = [c for c in all_status.collections if c.status in ("stale", "missing")]
        total_stale_profiles = sum(
            len([p for p in c.profiles if p.status in ("stale", "missing")]) for c in stale_collections
        )

        if not config.update_stale_caches:
            # Just report status
            logger.warning(
                f"Found {len(stale_collections)} collection(s) with {total_stale_profiles} stale/missing profile(s). "
                "Set update_stale_caches=true to auto-update on startup."
            )
            for collection in stale_collections:
                stale_profiles = [p for p in collection.profiles if p.status in ("stale", "missing")]
                logger.warning(f"  - {collection.collection_id}: {len(stale_profiles)} stale/missing profile(s)")
            return

        # Update stale caches
        logger.info(f"Updating {len(stale_collections)} stale collection(s)...")
        update_service = get_update_service()

        result = await update_service.update_all(
            check_only=False,
            force=False,  # Only update what's actually stale
        )

        if result.success:
            logger.info(f"Cache update completed: {result.successful_updates}/{result.total_profiles} profiles updated")
        else:
            logger.warning(
                f"Cache update completed with errors: "
                f"{result.successful_updates}/{result.total_profiles} succeeded, "
                f"{result.failed_updates} failed"
            )

    except Exception as e:
        logger.error(f"Failed to handle startup cache updates: {e}", exc_info=True)
        # Don't fail startup on cache update errors
