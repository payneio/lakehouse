"""Cache models for collections and profiles.

This module contains all data models for cache management including:
- Metadata models for persistent state (collections, profiles, dependencies)
- Change detection models for cache invalidation
- Status and result models for API responses
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from amplifier_library.models.base import CamelCaseModel


# =============================================================================
# Metadata Models
# =============================================================================


@dataclass
class CollectionMetadata:
    """Persistent metadata about a collection."""

    collection_id: str
    source_type: str  # 'git', 'local', 'registry'
    source_location: str
    mount_path: Path
    installed_at: datetime
    last_checked: datetime | None = None
    last_updated: datetime | None = None
    source_commit: str | None = None  # Git commit hash if from git

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "collection_id": self.collection_id,
            "source_type": self.source_type,
            "source_location": self.source_location,
            "mount_path": str(self.mount_path),
            "installed_at": self.installed_at.isoformat(),
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "source_commit": self.source_commit,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CollectionMetadata:
        """Load from dictionary."""
        return cls(
            collection_id=data["collection_id"],
            source_type=data["source_type"],
            source_location=data["source_location"],
            mount_path=Path(data["mount_path"]),
            installed_at=datetime.fromisoformat(data["installed_at"]),
            last_checked=(datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None),
            last_updated=(datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else None),
            source_commit=data.get("source_commit"),
        )


@dataclass
class ProfileDependency:
    """Dependency relationship between profiles."""

    dependent_profile_id: str
    dependency_profile_id: str
    dependency_type: str  # 'ref_mount', 'module_config', etc.
    added_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "dependent_profile_id": self.dependent_profile_id,
            "dependency_profile_id": self.dependency_profile_id,
            "dependency_type": self.dependency_type,
            "added_at": self.added_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProfileDependency:
        """Load from dictionary."""
        return cls(
            dependent_profile_id=data["dependent_profile_id"],
            dependency_profile_id=data["dependency_profile_id"],
            dependency_type=data["dependency_type"],
            added_at=datetime.fromisoformat(data["added_at"]),
        )


@dataclass
class ProfileMetadata:
    """Persistent metadata about a profile."""

    profile_id: str
    collection_id: str
    source_path: Path
    cache_path: Path | None
    source_modified: datetime
    cache_built: datetime | None
    manifest_hash: str  # Hash of manifest content for change detection
    last_checked: datetime | None = None
    dependencies: list[ProfileDependency] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "profile_id": self.profile_id,
            "collection_id": self.collection_id,
            "source_path": str(self.source_path),
            "cache_path": str(self.cache_path) if self.cache_path else None,
            "source_modified": self.source_modified.isoformat(),
            "cache_built": self.cache_built.isoformat() if self.cache_built else None,
            "manifest_hash": self.manifest_hash,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "dependencies": [dep.to_dict() for dep in (self.dependencies or [])],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProfileMetadata:
        """Load from dictionary."""
        dependencies = None
        if "dependencies" in data and data["dependencies"]:
            dependencies = [ProfileDependency.from_dict(dep) for dep in data["dependencies"]]
        return cls(
            profile_id=data["profile_id"],
            collection_id=data["collection_id"],
            source_path=Path(data["source_path"]),
            cache_path=Path(data["cache_path"]) if data.get("cache_path") else None,
            source_modified=datetime.fromisoformat(data["source_modified"]),
            cache_built=(datetime.fromisoformat(data["cache_built"]) if data.get("cache_built") else None),
            manifest_hash=data["manifest_hash"],
            last_checked=(datetime.fromisoformat(data["last_checked"]) if data.get("last_checked") else None),
            dependencies=dependencies,
        )

    @property
    def is_stale(self) -> bool:
        """Check if cache is stale (source newer than cache)."""
        if not self.cache_built:
            return True
        return self.source_modified > self.cache_built

    @property
    def cache_age_seconds(self) -> float | None:
        """Get cache age in seconds, if cache exists."""
        if not self.cache_built:
            return None
        return (datetime.now() - self.cache_built).total_seconds()


# =============================================================================
# Change Detection Models
# =============================================================================


@dataclass
class SourceChange:
    """Detected change in source files."""

    path: Path
    change_type: str  # 'modified', 'added', 'deleted'
    old_mtime: datetime | None
    new_mtime: datetime | None

    @property
    def is_modified(self) -> bool:
        """Whether this represents a modification."""
        return self.change_type == "modified"

    @property
    def is_added(self) -> bool:
        """Whether this represents an addition."""
        return self.change_type == "added"

    @property
    def is_deleted(self) -> bool:
        """Whether this represents a deletion."""
        return self.change_type == "deleted"


@dataclass
class ManifestChange:
    """Detected change in profile manifest."""

    profile_id: str
    field: str  # Which field changed (e.g., 'module_configs', 'ref_mounts')
    old_value: str | None
    new_value: str | None

    @property
    def summary(self) -> str:
        """Human-readable summary of the change."""
        if self.old_value is None:
            return f"{self.profile_id}: Added {self.field}"
        if self.new_value is None:
            return f"{self.profile_id}: Removed {self.field}"
        return f"{self.profile_id}: Changed {self.field}"


@dataclass
class DependencyChange:
    """Detected change in profile dependencies."""

    dependent_profile_id: str
    dependency_profile_id: str
    change_type: str  # 'added', 'removed', 'modified'

    @property
    def is_added(self) -> bool:
        """Whether this dependency was added."""
        return self.change_type == "added"

    @property
    def is_removed(self) -> bool:
        """Whether this dependency was removed."""
        return self.change_type == "removed"

    @property
    def is_modified(self) -> bool:
        """Whether this dependency was modified."""
        return self.change_type == "modified"


@dataclass
class ChangeReport:
    """Complete report of detected changes."""

    collection_id: str
    source_changes: list[SourceChange]
    manifest_changes: list[ManifestChange]
    dependency_changes: list[DependencyChange]
    detected_at: datetime

    @property
    def has_changes(self) -> bool:
        """Whether any changes were detected."""
        return bool(self.source_changes or self.manifest_changes or self.dependency_changes)

    @property
    def affected_profiles(self) -> set[str]:
        """Get all profile IDs affected by changes."""
        profiles = set()

        # Add profiles from manifest changes
        for change in self.manifest_changes:
            profiles.add(change.profile_id)

        # Add profiles from dependency changes
        for change in self.dependency_changes:
            profiles.add(change.dependent_profile_id)
            profiles.add(change.dependency_profile_id)

        return profiles

    @property
    def change_count(self) -> int:
        """Total number of changes detected."""
        return len(self.source_changes) + len(self.manifest_changes) + len(self.dependency_changes)

    def summary(self) -> str:
        """Generate human-readable summary."""
        if not self.has_changes:
            return f"No changes detected in {self.collection_id}"

        parts = []
        if self.source_changes:
            parts.append(f"{len(self.source_changes)} source file(s)")
        if self.manifest_changes:
            parts.append(f"{len(self.manifest_changes)} manifest change(s)")
        if self.dependency_changes:
            parts.append(f"{len(self.dependency_changes)} dependency change(s)")

        return f"{self.collection_id}: {', '.join(parts)}"


# =============================================================================
# Cache Status and Update Result Models (API responses)
# =============================================================================


class CacheTimestamps(CamelCaseModel):
    """Timestamps for cache validation."""

    source_modified: datetime | None = Field(
        None,
        description="When the source was last modified",
    )
    cache_built: datetime | None = Field(
        None,
        description="When the cache was last built",
    )


class ProfileCacheStatus(CamelCaseModel):
    """Cache status for a single profile."""

    profile_id: str = Field(
        ...,
        description="Profile identifier",
    )
    status: Literal["fresh", "stale", "missing"] = Field(
        ...,
        description="Cache status (fresh=up-to-date, stale=needs rebuild, missing=not cached)",
    )
    timestamps: CacheTimestamps = Field(
        ...,
        description="Source and cache timestamps",
    )
    source_path: str = Field(
        ...,
        description="Path to profile source",
    )
    cache_path: str | None = Field(
        None,
        description="Path to cached profile output",
    )


class CollectionCacheStatus(CamelCaseModel):
    """Cache status for a collection and its profiles."""

    collection_id: str = Field(
        ...,
        description="Collection identifier",
    )
    status: Literal["fresh", "stale", "missing"] = Field(
        ...,
        description="Overall collection cache status",
    )
    timestamps: CacheTimestamps = Field(
        ...,
        description="Collection timestamps",
    )
    profiles: list[ProfileCacheStatus] = Field(
        default_factory=list,
        description="Status of all profiles in the collection",
    )


class AllCacheStatus(CamelCaseModel):
    """Complete cache status for all collections."""

    collections: list[CollectionCacheStatus] = Field(
        default_factory=list,
        description="Status of all collections",
    )
    overall_status: Literal["fresh", "stale", "missing"] = Field(
        ...,
        description="Overall cache health (stale if any are stale/missing)",
    )


class UpdateResult(CamelCaseModel):
    """Base result for update operations."""

    success: bool = Field(
        ...,
        description="Whether the update succeeded",
    )
    message: str = Field(
        ...,
        description="Human-readable result message",
    )
    error: str | None = Field(
        None,
        description="Error details if update failed",
    )


class ProfileUpdateResult(UpdateResult):
    """Result of updating a single profile."""

    profile_id: str = Field(
        ...,
        description="Profile that was updated",
    )
    actions_taken: list[str] = Field(
        default_factory=list,
        description="List of actions performed (e.g., 'recompiled', 'cache-invalidated')",
    )
    cache_path: str | None = Field(
        None,
        description="Path to updated cache",
    )


class CollectionUpdateResult(CamelCaseModel):
    """Result of updating a collection."""

    collection_id: str = Field(
        ...,
        description="Collection that was updated",
    )
    success: bool = Field(
        ...,
        description="Whether all profile updates succeeded",
    )
    message: str = Field(
        ...,
        description="Summary of update operation",
    )
    profile_results: list[ProfileUpdateResult] = Field(
        default_factory=list,
        description="Results for each profile in the collection",
    )
    total_profiles: int = Field(
        0,
        description="Total number of profiles processed",
    )
    successful_updates: int = Field(
        0,
        description="Number of successful updates",
    )
    failed_updates: int = Field(
        0,
        description="Number of failed updates",
    )


class AllUpdateResult(CamelCaseModel):
    """Result of updating all collections."""

    success: bool = Field(
        ...,
        description="Whether all collection updates succeeded",
    )
    message: str = Field(
        ...,
        description="Summary of all updates",
    )
    collection_results: list[CollectionUpdateResult] = Field(
        default_factory=list,
        description="Results for each collection",
    )
    total_collections: int = Field(
        0,
        description="Total number of collections processed",
    )
    total_profiles: int = Field(
        0,
        description="Total number of profiles processed",
    )
    successful_updates: int = Field(
        0,
        description="Number of successful profile updates",
    )
    failed_updates: int = Field(
        0,
        description="Number of failed profile updates",
    )
