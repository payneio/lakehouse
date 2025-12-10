"""Metadata store service for collections and profiles.

Stores persistent metadata about collections, profiles, and their dependencies
using JSON files for efficient cache management and change detection.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime
from pathlib import Path

from amplifier_library.storage.paths import get_cache_dir

from .models import CollectionMetadata
from .models import ProfileDependency
from .models import ProfileMetadata

logger = logging.getLogger(__name__)


class MetadataStore:
    """JSON-based metadata store for collections and profiles."""

    def __init__(self, metadata_dir: Path | None = None) -> None:
        """Initialize metadata store.

        Args:
            metadata_dir: Root directory for metadata files.
                         Defaults to $AMPLIFIERD_HOME/cache/metadata
        """
        self.metadata_dir = metadata_dir or (get_cache_dir() / "metadata")
        self.collections_dir = self.metadata_dir / "collections"
        self.profiles_dir = self.metadata_dir / "profiles"

        # Ensure directories exist
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized metadata store at {self.metadata_dir}")

    def _save_json(self, path: Path, data: dict) -> None:
        """Save dict as JSON file atomically.

        Args:
            path: Target file path
            data: Dictionary to save as JSON
        """
        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first
        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str, ensure_ascii=False)
            # Atomic rename
            temp_path.rename(path)
            logger.debug(f"Saved JSON to {path}")
        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save JSON to {path}: {e}") from e

    def _load_json(self, path: Path) -> dict | None:
        """Load JSON file or return None if not found.

        Args:
            path: File path to load

        Returns:
            Dictionary from JSON file, or None if file doesn't exist
        """
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load JSON from {path}: {e}")
            return None

    def _sanitize_collection_id(self, collection_id: str) -> str:
        """Sanitize collection ID for use as filename.

        Args:
            collection_id: Collection identifier

        Returns:
            Sanitized collection ID safe for filesystem
        """
        # Replace problematic characters with underscores
        return collection_id.replace("/", "_").replace("\\", "_")

    # Collection operations

    def get_collection(self, collection_id: str) -> CollectionMetadata | None:
        """Get collection metadata.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection metadata if found, None otherwise
        """
        safe_id = self._sanitize_collection_id(collection_id)
        path = self.collections_dir / f"{safe_id}.json"
        data = self._load_json(path)
        if data:
            return CollectionMetadata.from_dict(data)
        return None

    def save_collection(self, metadata: CollectionMetadata) -> None:
        """Save or update collection metadata.

        Args:
            metadata: Collection metadata to save
        """
        safe_id = self._sanitize_collection_id(metadata.collection_id)
        path = self.collections_dir / f"{safe_id}.json"
        data = metadata.to_dict()
        self._save_json(path, data)
        logger.debug(f"Saved collection metadata: {metadata.collection_id}")

    def list_collections(self) -> list[CollectionMetadata]:
        """List all collections.

        Returns:
            List of all collection metadata
        """
        collections = []
        for json_file in sorted(self.collections_dir.glob("*.json")):
            data = self._load_json(json_file)
            if data:
                try:
                    collections.append(CollectionMetadata.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load collection from {json_file}: {e}")
        return collections

    def delete_collection(self, collection_id: str) -> None:
        """Delete collection metadata and all its profiles.

        Args:
            collection_id: Collection to delete
        """
        safe_id = self._sanitize_collection_id(collection_id)
        collection_path = self.collections_dir / f"{safe_id}.json"

        # Delete collection file
        if collection_path.exists():
            collection_path.unlink()
            logger.debug(f"Deleted collection metadata: {collection_id}")

        # Delete all profiles for this collection
        profile_collection_dir = self.profiles_dir / safe_id
        if profile_collection_dir.exists():
            # Delete all profile JSON files
            for profile_file in profile_collection_dir.glob("*.json"):
                profile_file.unlink()
            # Remove empty directory
            with contextlib.suppress(OSError):
                profile_collection_dir.rmdir()

    # Profile operations

    def get_profile(self, collection_id: str, profile_id: str) -> ProfileMetadata | None:
        """Get profile metadata.

        Args:
            collection_id: Collection identifier
            profile_id: Profile identifier

        Returns:
            Profile metadata if found, None otherwise
        """
        safe_collection_id = self._sanitize_collection_id(collection_id)
        path = self.profiles_dir / safe_collection_id / f"{profile_id}.json"
        data = self._load_json(path)
        if data:
            return ProfileMetadata.from_dict(data)
        return None

    def save_profile(self, metadata: ProfileMetadata) -> None:
        """Save or update profile metadata.

        Args:
            metadata: Profile metadata to save
        """
        safe_collection_id = self._sanitize_collection_id(metadata.collection_id)
        profile_dir = self.profiles_dir / safe_collection_id
        profile_dir.mkdir(parents=True, exist_ok=True)

        path = profile_dir / f"{metadata.profile_id}.json"
        data = metadata.to_dict()
        self._save_json(path, data)
        logger.debug(f"Saved profile metadata: {metadata.profile_id}")

    def list_profiles(self, collection_id: str | None = None) -> list[ProfileMetadata]:
        """List profiles, optionally filtered by collection.

        Args:
            collection_id: Optional collection to filter by

        Returns:
            List of profile metadata
        """
        profiles = []

        if collection_id:
            # List profiles for specific collection
            safe_collection_id = self._sanitize_collection_id(collection_id)
            profile_dir = self.profiles_dir / safe_collection_id
            if profile_dir.exists():
                for json_file in sorted(profile_dir.glob("*.json")):
                    data = self._load_json(json_file)
                    if data:
                        try:
                            profiles.append(ProfileMetadata.from_dict(data))
                        except Exception as e:
                            logger.warning(f"Failed to load profile from {json_file}: {e}")
        else:
            # List all profiles across all collections
            for collection_dir in sorted(self.profiles_dir.iterdir()):
                if collection_dir.is_dir():
                    for json_file in sorted(collection_dir.glob("*.json")):
                        data = self._load_json(json_file)
                        if data:
                            try:
                                profiles.append(ProfileMetadata.from_dict(data))
                            except Exception as e:
                                logger.warning(f"Failed to load profile from {json_file}: {e}")

        return profiles

    def delete_profile(self, collection_id: str, profile_id: str) -> None:
        """Delete profile metadata.

        Args:
            collection_id: Collection identifier
            profile_id: Profile to delete
        """
        safe_collection_id = self._sanitize_collection_id(collection_id)
        path = self.profiles_dir / safe_collection_id / f"{profile_id}.json"

        if path.exists():
            path.unlink()
            logger.debug(f"Deleted profile metadata: {profile_id}")

    def list_stale_profiles(self, collection_id: str | None = None) -> list[ProfileMetadata]:
        """List profiles with stale caches.

        A profile is stale if:
        - It has no cache (cache_built is None)
        - Its source was modified after the cache was built

        Args:
            collection_id: Optional collection to filter by

        Returns:
            List of stale profile metadata
        """
        all_profiles = self.list_profiles(collection_id)
        return [p for p in all_profiles if p.is_stale]

    # Dependency operations

    def add_dependency(self, dependency: ProfileDependency) -> None:
        """Add a profile dependency.

        Args:
            dependency: Dependency to add
        """
        # Load the profile
        profile = self.get_profile(
            dependency.dependent_profile_id.split("/")[0],  # Extract collection_id
            dependency.dependent_profile_id,
        )
        if not profile:
            logger.warning(f"Cannot add dependency: profile {dependency.dependent_profile_id} not found")
            return

        # Initialize dependencies list if needed
        if profile.dependencies is None:
            profile.dependencies = []

        # Check if dependency already exists
        existing = any(
            d.dependency_profile_id == dependency.dependency_profile_id
            and d.dependency_type == dependency.dependency_type
            for d in profile.dependencies
        )

        if not existing:
            profile.dependencies.append(dependency)
            self.save_profile(profile)
            logger.debug(f"Added dependency: {dependency.dependent_profile_id} -> {dependency.dependency_profile_id}")

    def get_dependencies(self, collection_id: str, profile_id: str) -> list[ProfileDependency]:
        """Get all dependencies of a profile.

        Args:
            collection_id: Collection identifier
            profile_id: Profile to get dependencies for

        Returns:
            List of dependencies
        """
        profile = self.get_profile(collection_id, profile_id)
        if profile and profile.dependencies:
            return profile.dependencies
        return []

    def get_dependents(self, profile_id: str) -> list[ProfileDependency]:
        """Get all profiles that depend on this profile.

        Args:
            profile_id: Profile to get dependents for

        Returns:
            List of dependencies where this profile is the dependency
        """
        dependents = []
        for profile in self.list_profiles():
            if profile.dependencies:
                for dep in profile.dependencies:
                    if dep.dependency_profile_id == profile_id:
                        dependents.append(dep)
        return dependents

    def clear_dependencies(self, collection_id: str, profile_id: str) -> None:
        """Clear all dependencies of a profile.

        Args:
            collection_id: Collection identifier
            profile_id: Profile to clear dependencies for
        """
        profile = self.get_profile(collection_id, profile_id)
        if profile:
            profile.dependencies = []
            self.save_profile(profile)
            logger.debug(f"Cleared dependencies for profile: {profile_id}")

    # Utility operations

    def list_stale_collections(self) -> list[str]:
        """List collections that have at least one stale profile.

        Returns:
            List of collection IDs with stale profiles
        """
        stale_collections = set()
        for profile in self.list_profiles():
            if profile.is_stale:
                stale_collections.add(profile.collection_id)
        return sorted(stale_collections)

    def update_last_checked(
        self,
        collection_id: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        """Update last_checked timestamp.

        Args:
            collection_id: Optional collection to update
            profile_id: Optional profile to update (requires collection_id)
        """
        now = datetime.now()

        if collection_id and not profile_id:
            # Update collection
            collection = self.get_collection(collection_id)
            if collection:
                collection.last_checked = now
                self.save_collection(collection)

        if collection_id and profile_id:
            # Update profile
            profile = self.get_profile(collection_id, profile_id)
            if profile:
                profile.last_checked = now
                self.save_profile(profile)

    def close(self) -> None:
        """Close the metadata store.

        This is a no-op for JSON-based storage,
        but provided for API consistency.
        """
        pass
