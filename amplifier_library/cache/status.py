"""Status service for querying cache state.

Provides read-only queries for cache status without modifying state.
"""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from .metadata_store import MetadataStore
from .models import AllCacheStatus
from .models import CacheTimestamps
from .models import CollectionCacheStatus
from .models import ProfileCacheStatus

logger = logging.getLogger(__name__)


class StatusService:
    """Service for querying cache status (read-only)."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        check_interval_hours: int = 24,
    ) -> None:
        """Initialize status service.

        Args:
            metadata_store: Metadata store for cached state
            check_interval_hours: How often to check for updates (default 24h)
        """
        self.metadata_store = metadata_store
        self.check_interval = timedelta(hours=check_interval_hours)
        logger.info(f"Initialized StatusService (check interval: {check_interval_hours}h)")

    def get_collection_status(self, collection_id: str) -> CollectionCacheStatus | None:
        """Get status of one collection.

        Args:
            collection_id: Collection to query

        Returns:
            Collection cache status if found, None otherwise
        """
        collection = self.metadata_store.get_collection(collection_id)
        if not collection:
            logger.warning(f"Collection not found: {collection_id}")
            return None

        # Get all profiles for this collection
        profiles = self.metadata_store.list_profiles(collection_id)
        profile_statuses = [self._get_profile_status_from_metadata(p) for p in profiles]

        # Determine overall collection status
        if not profile_statuses or any(p.status == "missing" for p in profile_statuses):
            status = "missing"
        elif any(p.status == "stale" for p in profile_statuses):
            status = "stale"
        else:
            status = "fresh"

        return CollectionCacheStatus(
            collection_id=collection_id,
            status=status,
            timestamps=CacheTimestamps(
                source_modified=collection.last_updated,
                cache_built=collection.last_updated,
            ),
            profiles=profile_statuses,
        )

    def get_profile_status(
        self,
        collection_id: str,
        profile_id: str,
    ) -> ProfileCacheStatus | None:
        """Get status of one profile.

        Args:
            collection_id: Collection containing profile
            profile_id: Profile to query

        Returns:
            Profile cache status if found, None otherwise
        """
        profile = self.metadata_store.get_profile(collection_id, profile_id)
        if not profile:
            logger.warning(f"Profile not found: {profile_id}")
            return None

        if profile.collection_id != collection_id:
            logger.warning(f"Profile {profile_id} belongs to {profile.collection_id}, not {collection_id}")
            return None

        return self._get_profile_status_from_metadata(profile)

    def _get_profile_status_from_metadata(self, profile) -> ProfileCacheStatus:
        """Convert profile metadata to cache status.

        Args:
            profile: ProfileMetadata object

        Returns:
            ProfileCacheStatus
        """
        # Determine status
        if not profile.cache_built:
            status = "missing"
        elif profile.is_stale:
            status = "stale"
        else:
            status = "fresh"

        return ProfileCacheStatus(
            profile_id=profile.profile_id,
            status=status,
            timestamps=CacheTimestamps(
                source_modified=profile.source_modified,
                cache_built=profile.cache_built,
            ),
            source_path=str(profile.source_path),
            cache_path=str(profile.cache_path) if profile.cache_path else None,
        )

    def get_all_status(self) -> AllCacheStatus:
        """Get status of all collections and profiles.

        Returns:
            Complete cache status
        """
        collections = self.metadata_store.list_collections()
        collection_statuses = []

        for collection in collections:
            status = self.get_collection_status(collection.collection_id)
            if status:
                collection_statuses.append(status)

        # Determine overall status
        if not collection_statuses or any(c.status == "missing" for c in collection_statuses):
            overall_status = "missing"
        elif any(c.status == "stale" for c in collection_statuses):
            overall_status = "stale"
        else:
            overall_status = "fresh"

        return AllCacheStatus(
            collections=collection_statuses,
            overall_status=overall_status,
        )

    def list_stale_collections(self) -> list[str]:
        """List collection IDs needing updates.

        Returns:
            List of collection IDs with stale or missing caches
        """
        return self.metadata_store.list_stale_collections()

    def list_stale_profiles(self, collection_id: str) -> list[str]:
        """List profile IDs in collection needing updates.

        Args:
            collection_id: Collection to check

        Returns:
            List of profile IDs with stale or missing caches
        """
        stale_profiles = self.metadata_store.list_stale_profiles(collection_id)
        return [p.profile_id for p in stale_profiles]

    def should_check_collection(self, collection_id: str) -> bool:
        """Check if collection is due for a check.

        Args:
            collection_id: Collection to check

        Returns:
            True if check is due based on check_interval
        """
        collection = self.metadata_store.get_collection(collection_id)
        if not collection:
            return True  # Missing collection should be checked

        if not collection.last_checked:
            return True  # Never checked

        # Check if interval has elapsed
        time_since_check = datetime.now(UTC) - collection.last_checked
        return time_since_check >= self.check_interval

    def should_check_profile(self, collection_id: str, profile_id: str) -> bool:
        """Check if profile is due for a check.

        Args:
            collection_id: Collection containing profile
            profile_id: Profile to check

        Returns:
            True if check is due based on check_interval
        """
        profile = self.metadata_store.get_profile(collection_id, profile_id)
        if not profile:
            return True  # Missing profile should be checked

        if not profile.last_checked:
            return True  # Never checked

        # Check if interval has elapsed
        time_since_check = datetime.now(UTC) - profile.last_checked
        return time_since_check >= self.check_interval
