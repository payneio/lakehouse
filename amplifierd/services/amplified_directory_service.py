"""Amplified directory management service."""

import json
import logging
import os
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path
from threading import Lock

from amplifierd.models.amplified_directories import AmplifiedDirectory
from amplifierd.models.amplified_directories import AmplifiedDirectoryCreate
from amplifierd.models.amplified_directories import AmplifiedDirectoryUpdate

logger = logging.getLogger(__name__)


class AmplifiedDirectoryService:
    """Service for managing amplified directories.

    Handles discovery, registration, and metadata management for directories
    containing .amplified markers.

    Security-critical: All paths are validated to prevent directory traversal.
    """

    def __init__(self, data_path: Path, cache_ttl: int = 30, max_scan_depth: int = 10) -> None:
        """Initialize with root working directory.

        Args:
            data_path: Root directory (AMPLIFIERD_DATA_PATH)
            cache_ttl: Cache time-to-live in seconds (default: 30)
            max_scan_depth: Maximum directory depth to scan (default: 10)
        """
        self.root = Path(data_path).resolve()

        # Performance: Cache for list_all()
        self._cache: list[AmplifiedDirectory] | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = cache_ttl
        self._cache_lock = Lock()
        self._max_scan_depth: int = max_scan_depth

    def _resolve_default_profile(self, relative_path: str, provided_profile: str | None) -> str:
        """Resolve default profile for directory.

        Resolution order:
        1. If provided_profile given → use it
        2. Else → find parent amplified directory and use its default_profile
        3. If no parent → use root's default_profile
        4. Root uses AMPLIFIERD_DEFAULT_PROFILE env var (default: foundation/foundation)
        """
        if provided_profile:
            logger.debug(f"Using provided profile: {provided_profile}")
            return provided_profile

        parent_path = self._find_parent_amplified_directory(relative_path)

        if parent_path:
            parent_metadata = self._read_metadata(parent_path)
            if parent_metadata and "default_profile" in parent_metadata:
                inherited_profile = parent_metadata["default_profile"]
                logger.debug(f"Inheriting profile from parent {parent_path}: {inherited_profile}")
                return inherited_profile

        default_profile = os.getenv("AMPLIFIERD_DEFAULT_PROFILE", "foundation/foundation")
        logger.debug(f"Using default profile from environment: {default_profile}")
        return default_profile

    def _find_parent_amplified_directory(self, relative_path: str) -> Path | None:
        """Find nearest parent amplified directory.

        Walks up directory tree to find parent with .amplified marker.
        """
        path = Path(relative_path)

        for parent in path.parents:
            if str(parent) == ".":
                root_marker = self.root / ".amplified"
                if root_marker.exists() and root_marker.is_dir():
                    return self.root
                return None

            parent_abs = self.root / parent
            parent_marker = parent_abs / ".amplified"

            if parent_marker.exists() and parent_marker.is_dir():
                return parent_abs

        root_marker = self.root / ".amplified"
        if root_marker.exists() and root_marker.is_dir():
            return self.root

        return None

    def create(self, create_req: AmplifiedDirectoryCreate) -> AmplifiedDirectory:
        """Register/create amplified directory with profile inheritance.

        Args:
            create_req: Creation request with relative path and metadata

        Returns:
            AmplifiedDirectory instance

        Raises:
            ValueError: If path is invalid or directory already amplified
            OSError: If directory/marker creation fails

        Side Effects:
            - Creates target directory if missing
            - Creates .amplified marker directory if create_marker=True
            - Writes metadata.json with default_profile
        """
        dir_path = self._validate_and_resolve_path(create_req.relative_path)

        if self.is_amplified(create_req.relative_path):
            raise ValueError(f"Directory already amplified: {create_req.relative_path}")

        try:
            default_profile = self._resolve_default_profile(create_req.relative_path, create_req.default_profile)

            metadata = create_req.metadata.copy() if create_req.metadata else {}
            metadata["default_profile"] = default_profile

            dir_path.mkdir(parents=True, exist_ok=True)

            if create_req.create_marker:
                marker_path = self._get_marker_path(dir_path)
                marker_path.mkdir(exist_ok=True)

            self._write_metadata(dir_path, metadata)

            now = datetime.now(UTC)
            amplified_dir = AmplifiedDirectory(
                relative_path=create_req.relative_path,
                default_profile=metadata.get("default_profile"),
                metadata=metadata,
                created_at=now,
                last_used_at=None,
                path=str(dir_path),
                is_amplified=True,
            )

            logger.info(f"Created amplified directory: {create_req.relative_path} with profile: {default_profile}")

            # Invalidate cache so new directory appears in list
            self.invalidate_cache()

            return amplified_dir

        except Exception as e:
            logger.error(f"Failed to create amplified directory {create_req.relative_path}: {e}")
            raise

    def get(self, relative_path: str) -> AmplifiedDirectory | None:
        """Get specific amplified directory.

        Args:
            relative_path: Path relative to root

        Returns:
            AmplifiedDirectory if exists and is amplified, None otherwise

        Raises:
            ValueError: If path is invalid
        """
        try:
            dir_path = self._validate_and_resolve_path(relative_path)
            marker_path = self._get_marker_path(dir_path)

            if not marker_path.exists() or not marker_path.is_dir():
                return None

            metadata = self._read_metadata(dir_path)

            if not metadata:
                logger.warning(f"Amplified directory {relative_path} has no metadata.json")
                return None

            if "default_profile" not in metadata:
                logger.warning(f"Amplified directory {relative_path} missing default_profile in metadata")

            # Extract default_profile from metadata for top-level field
            default_profile = metadata.get("default_profile")

            now = datetime.now(UTC)
            return AmplifiedDirectory(
                relative_path=relative_path,
                default_profile=default_profile,
                metadata=metadata,
                created_at=now,
                last_used_at=None,
                path=str(dir_path),
                is_amplified=True,
            )

        except ValueError:
            return None

    def list_all(self, force_refresh: bool = False) -> list[AmplifiedDirectory]:
        """Discover all amplified directories under root (cached).

        Args:
            force_refresh: If True, bypass cache and rescan filesystem

        Returns:
            List of AmplifiedDirectory instances

        Implementation:
            Uses in-memory cache with TTL for performance.
            First request or cache expiration triggers filesystem scan.
            Cache invalidated automatically on create/update/delete.
        """
        now = time.time()

        # Check cache (thread-safe)
        with self._cache_lock:
            if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
                logger.debug(f"Returning cached directories ({len(self._cache)} entries)")
                return self._cache

        # Scan filesystem (outside lock to allow other reads)
        logger.info("Scanning for amplified directories...")
        directories = self._scan_filesystem()

        # Update cache (thread-safe)
        with self._cache_lock:
            self._cache = directories
            self._cache_time = now

        logger.info(f"Found {len(directories)} amplified directories (cached for {self._cache_ttl}s)")
        return directories

    def _scan_filesystem(self) -> list[AmplifiedDirectory]:
        """Scan filesystem for amplified directories.

        Returns:
            List of AmplifiedDirectory instances

        Implementation:
            Uses Path.rglob(".amplified") to find all markers,
            respects max_scan_depth to prevent runaway scans.
        """
        directories: list[AmplifiedDirectory] = []

        for marker_path in self.root.rglob(".amplified"):
            # Depth check (prevent excessive scanning)
            try:
                depth = len(marker_path.relative_to(self.root).parts)
                if depth > self._max_scan_depth:
                    logger.warning(f"Skipping {marker_path} - exceeds max depth {self._max_scan_depth}")
                    continue
            except ValueError:
                # Path not relative to root (shouldn't happen but be safe)
                continue

            if not marker_path.is_dir():
                continue

            dir_path = marker_path.parent

            try:
                relative_path = str(dir_path.relative_to(self.root))
                metadata = self._read_metadata(dir_path)

                if not metadata:
                    logger.warning(f"Skipping amplified directory {relative_path} - no metadata.json")
                    continue

                if "default_profile" not in metadata:
                    logger.warning(f"Amplified directory {relative_path} missing default_profile")

                directories.append(
                    AmplifiedDirectory(
                        relative_path=relative_path,
                        default_profile=metadata.get("default_profile"),
                        metadata=metadata,
                        created_at=datetime.now(UTC),
                        last_used_at=None,
                        path=str(dir_path),
                        is_amplified=True,
                    )
                )

            except Exception as e:
                logger.warning(f"Failed to process amplified directory {dir_path}: {e}")
                continue

        return directories

    def invalidate_cache(self) -> None:
        """Invalidate cache, forcing next list_all() to rescan filesystem."""
        with self._cache_lock:
            self._cache = None
            self._cache_time = 0
        logger.debug("Directory cache invalidated")

    def update(
        self,
        relative_path: str,
        update_req: AmplifiedDirectoryUpdate,
    ) -> AmplifiedDirectory | None:
        """Update amplified directory metadata.

        Args:
            relative_path: Path relative to root
            update_req: Update request with new metadata

        Returns:
            Updated AmplifiedDirectory if exists, None otherwise

        Raises:
            ValueError: If path is invalid
            OSError: If metadata write fails

        Side Effects:
            Writes metadata.json atomically (tmp + rename)
        """
        # Validate and resolve path
        dir_path = self._validate_and_resolve_path(relative_path)

        # Check if amplified
        if not self._get_marker_path(dir_path).exists():
            return None

        try:
            # Read existing metadata
            existing_metadata = self._read_metadata(dir_path) or {}

            # Merge default_profile if provided
            if update_req.default_profile is not None:
                existing_metadata["default_profile"] = update_req.default_profile

            # Merge metadata if provided
            if update_req.metadata is not None:
                existing_metadata.update(update_req.metadata)

            # Write merged metadata
            self._write_metadata(dir_path, existing_metadata)

            # Invalidate cache to reflect updated metadata
            self.invalidate_cache()

            # Return updated directory
            return self.get(relative_path)

        except Exception as e:
            logger.error(f"Failed to update amplified directory {relative_path}: {e}")
            raise

    def delete(self, relative_path: str, remove_marker: bool = False) -> bool:
        """Unregister amplified directory.

        Args:
            relative_path: Path relative to root
            remove_marker: If True, remove .amplified directory

        Returns:
            True if directory was amplified and unregistered, False otherwise

        Raises:
            ValueError: If path is invalid
            OSError: If marker removal fails

        Side Effects:
            Removes .amplified directory if remove_marker=True
        """
        try:
            # Validate and resolve path
            dir_path = self._validate_and_resolve_path(relative_path)

            # Check if amplified
            marker_path = self._get_marker_path(dir_path)
            if not marker_path.exists():
                return False

            # Remove marker if requested
            if remove_marker:
                import shutil

                shutil.rmtree(marker_path)
                logger.info(f"Removed amplified marker: {relative_path}")

            # Invalidate cache so deleted directory no longer appears
            self.invalidate_cache()

            return True

        except Exception as e:
            logger.error(f"Failed to delete amplified directory {relative_path}: {e}")
            raise

    def is_amplified(self, relative_path: str) -> bool:
        """Check if directory is amplified.

        Args:
            relative_path: Path relative to root

        Returns:
            True if directory contains .amplified marker, False otherwise

        Raises:
            ValueError: If path is invalid
        """
        try:
            # Validate and resolve path
            dir_path = self._validate_and_resolve_path(relative_path)

            # Check for marker
            return self._get_marker_path(dir_path).exists()

        except ValueError:
            # Invalid path
            return False

    # --- Private Helper Methods ---

    def _validate_and_resolve_path(self, relative_path: str) -> Path:
        """Validate and resolve path (security-critical).

        Args:
            relative_path: Path relative to root

        Returns:
            Resolved absolute Path within root

        Raises:
            ValueError: If path is invalid or escapes root

        Security Requirements:
            1. Reject absolute paths
            2. Reject paths containing '..'
            3. Resolve symlinks and verify containment
        """
        # Convert to Path
        path = Path(relative_path)

        # 1. Reject absolute paths
        if path.is_absolute():
            raise ValueError(f"Path must be relative: {relative_path}")

        # 2. Reject paths containing '..'
        if any(part == ".." for part in path.parts):
            raise ValueError(f"Path cannot contain '..': {relative_path}")

        # 3. Resolve symlinks and verify containment
        full_path = (self.root / path).resolve()

        # Verify path is within root (relative_to raises ValueError if not)
        try:
            full_path.relative_to(self.root)
        except ValueError:
            raise ValueError(f"Path escapes root: {relative_path}")

        return full_path

    def _get_marker_path(self, dir_path: Path) -> Path:
        """Get .amplified directory path.

        Args:
            dir_path: Absolute directory path

        Returns:
            Path to .amplified directory
        """
        return dir_path / ".amplified"

    def _get_metadata_path(self, dir_path: Path) -> Path:
        """Get metadata.json path.

        Args:
            dir_path: Absolute directory path

        Returns:
            Path to metadata.json file
        """
        return self._get_marker_path(dir_path) / "metadata.json"

    def _read_metadata(self, dir_path: Path) -> dict | None:
        """Read metadata from filesystem.

        Args:
            dir_path: Absolute directory path

        Returns:
            Metadata dict if exists, None otherwise

        Handles JSON errors gracefully (logs warning and returns None).
        """
        metadata_path = self._get_metadata_path(dir_path)

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path) as f:
                return json.load(f)

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read metadata from {metadata_path}: {e}")
            return None

    def _write_metadata(self, dir_path: Path, metadata: dict) -> None:
        """Write metadata to filesystem atomically.

        Args:
            dir_path: Absolute directory path
            metadata: Metadata dict to write

        Raises:
            OSError: If write fails

        Implementation:
            Uses tmp + rename pattern for atomic writes.
        """
        metadata_path = self._get_metadata_path(dir_path)

        # Ensure .amplified directory exists
        metadata_path.parent.mkdir(exist_ok=True)

        # Write to tmp file
        tmp_path = metadata_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Rename to metadata.json (atomic)
            tmp_path.rename(metadata_path)

        except Exception:
            # Cleanup tmp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise
