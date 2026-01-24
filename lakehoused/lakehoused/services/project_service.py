"""Project management service."""

import json
import logging
import os
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path
from threading import Lock

from lakehoused.models.projects import Project
from lakehoused.models.projects import ProjectCreate
from lakehoused.models.projects import ProjectUpdate

logger = logging.getLogger(__name__)


class ProjectService:
    """Service for managing projects.

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
        self._cache: list[Project] | None = None
        self._cache_time: float = 0
        self._cache_ttl: float = cache_ttl
        self._cache_lock = Lock()
        self._max_scan_depth: int = max_scan_depth

    def _resolve_default_bundle(self, relative_path: str, provided_profile: str | None) -> str:
        """Resolve default profile for directory.

        Resolution order:
        1. If provided_profile given → use it
        2. Else → find parent project and use its default_bundle
        3. If no parent → use root's default_bundle
        4. Root uses AMPLIFIERD_DEFAULT_BUNDLE env var (default: foundation/foundation)
        """
        if provided_profile:
            logger.debug(f"Using provided profile: {provided_profile}")
            return provided_profile

        parent_path = self._find_parent_project(relative_path)

        if parent_path:
            parent_metadata = self._read_metadata(parent_path)
            if parent_metadata and "default_bundle" in parent_metadata:
                inherited_profile = parent_metadata["default_bundle"]
                logger.debug(f"Inheriting profile from parent {parent_path}: {inherited_profile}")
                return inherited_profile

        default_bundle = os.getenv("AMPLIFIERD_DEFAULT_BUNDLE", "foundation/foundation")
        logger.debug(f"Using default profile from environment: {default_bundle}")
        return default_bundle

    def _find_parent_project(self, relative_path: str) -> Path | None:
        """Find nearest parent project.

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

    def create(self, create_req: ProjectCreate) -> Project:
        """Register/create project with profile inheritance.

        Args:
            create_req: Creation request with relative path and metadata

        Returns:
            Project instance

        Raises:
            ValueError: If path is invalid or directory already a project
            OSError: If directory/marker creation fails

        Side Effects:
            - Creates target directory if missing
            - Creates .amplified marker directory if create_marker=True
            - Writes metadata.json with default_bundle
        """
        dir_path = self._validate_and_resolve_path(create_req.relative_path)

        if self.is_project(create_req.relative_path):
            raise ValueError(f"Directory is already a project: {create_req.relative_path}")

        try:
            default_bundle = self._resolve_default_bundle(create_req.relative_path, create_req.default_bundle)

            metadata = create_req.metadata.copy() if create_req.metadata else {}
            metadata["default_bundle"] = default_bundle

            dir_path.mkdir(parents=True, exist_ok=True)

            if create_req.create_marker:
                marker_path = self._get_marker_path(dir_path)
                marker_path.mkdir(exist_ok=True)

            self._write_metadata(dir_path, metadata)

            now = datetime.now(UTC)
            project = Project(
                relative_path=create_req.relative_path,
                default_bundle=metadata.get("default_bundle"),
                metadata=metadata,
                created_at=now,
                last_used_at=None,
                path=str(dir_path),
                is_project=True,
            )

            logger.info(f"Created project: {create_req.relative_path} with profile: {default_bundle}")

            # Invalidate cache so new project appears in list
            self.invalidate_cache()

            return project

        except Exception as e:
            logger.error(f"Failed to create project {create_req.relative_path}: {e}")
            raise

    def get(self, relative_path: str) -> Project | None:
        """Get specific project.

        Args:
            relative_path: Path relative to root

        Returns:
            Project if exists and is a project, None otherwise

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
                logger.warning(f"Project {relative_path} has no metadata.json")
                return None

            if "default_bundle" not in metadata:
                logger.warning(f"Project {relative_path} missing default_bundle in metadata")

            # Extract default_bundle from metadata for top-level field
            default_bundle = metadata.get("default_bundle")

            # Read AGENTS.md content
            agents_content = self._read_agents_file(dir_path)

            now = datetime.now(UTC)
            return Project(
                relative_path=relative_path,
                default_bundle=default_bundle,
                metadata=metadata,
                agents_content=agents_content,
                created_at=now,
                last_used_at=None,
                path=str(dir_path),
                is_project=True,
            )

        except ValueError:
            return None

    def list_all(self, force_refresh: bool = False) -> list[Project]:
        """Discover all projects under root (cached).

        Args:
            force_refresh: If True, bypass cache and rescan filesystem

        Returns:
            List of Project instances

        Implementation:
            Uses in-memory cache with TTL for performance.
            First request or cache expiration triggers filesystem scan.
            Cache invalidated automatically on create/update/delete.
        """
        now = time.time()

        # Check cache (thread-safe)
        with self._cache_lock:
            if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl:
                logger.debug(f"Returning cached projects ({len(self._cache)} entries)")
                return self._cache

        # Scan filesystem (outside lock to allow other reads)
        logger.info("Scanning for projects...")
        projects = self._scan_filesystem()

        # Update cache (thread-safe)
        with self._cache_lock:
            self._cache = projects
            self._cache_time = now

        logger.info(f"Found {len(projects)} projects (cached for {self._cache_ttl}s)")
        return projects

    def _scan_filesystem(self) -> list[Project]:
        """Scan filesystem for projects.

        Returns:
            List of Project instances

        Implementation:
            Uses Path.rglob(".amplified") to find all markers,
            respects max_scan_depth to prevent runaway scans.
        """
        projects: list[Project] = []

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
                    logger.warning(f"Skipping project {relative_path} - no metadata.json")
                    continue

                if "default_bundle" not in metadata:
                    logger.warning(f"Project {relative_path} missing default_bundle")

                # Read AGENTS.md content
                agents_content = self._read_agents_file(dir_path)

                projects.append(
                    Project(
                        relative_path=relative_path,
                        default_bundle=metadata.get("default_bundle"),
                        metadata=metadata,
                        agents_content=agents_content,
                        created_at=datetime.now(UTC),
                        last_used_at=None,
                        path=str(dir_path),
                        is_project=True,
                    )
                )

            except Exception as e:
                logger.warning(f"Failed to process project {dir_path}: {e}")
                continue

        return projects

    def invalidate_cache(self) -> None:
        """Invalidate cache, forcing next list_all() to rescan filesystem."""
        with self._cache_lock:
            self._cache = None
            self._cache_time = 0
        logger.debug("Project cache invalidated")

    def update(
        self,
        relative_path: str,
        update_req: ProjectUpdate,
    ) -> Project | None:
        """Update project metadata.

        Args:
            relative_path: Path relative to root
            update_req: Update request with new metadata

        Returns:
            Updated Project if exists, None otherwise

        Raises:
            ValueError: If path is invalid
            OSError: If metadata write fails

        Side Effects:
            Writes metadata.json atomically (tmp + rename)
        """
        # Validate and resolve path
        dir_path = self._validate_and_resolve_path(relative_path)

        # Check if project
        if not self._get_marker_path(dir_path).exists():
            return None

        try:
            # Read existing metadata
            existing_metadata = self._read_metadata(dir_path) or {}

            # Merge default_bundle if provided
            if update_req.default_bundle is not None:
                existing_metadata["default_bundle"] = update_req.default_bundle

            # Merge metadata if provided
            if update_req.metadata is not None:
                existing_metadata.update(update_req.metadata)

            # Write merged metadata
            self._write_metadata(dir_path, existing_metadata)

            # Invalidate cache to reflect updated metadata
            self.invalidate_cache()

            # Return updated project
            return self.get(relative_path)

        except Exception as e:
            logger.error(f"Failed to update project {relative_path}: {e}")
            raise

    def update_agents_content(self, relative_path: str, agents_content: str) -> bool:
        """Update AGENTS.md file for a project.

        Args:
            relative_path: Path relative to root
            agents_content: New content for AGENTS.md

        Returns:
            True if updated successfully

        Raises:
            ValueError: If path is invalid
            OSError: If write fails
        """
        # Validate and resolve path
        dir_path = self._validate_and_resolve_path(relative_path)

        # Check if project
        if not self._get_marker_path(dir_path).exists():
            return False

        try:
            # Write agents file
            self._write_agents_file(dir_path, agents_content)

            logger.info(f"Updated AGENTS.md for {relative_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to update AGENTS.md for {relative_path}: {e}")
            raise

    def delete(self, relative_path: str, remove_marker: bool = False) -> bool:
        """Unregister project.

        Args:
            relative_path: Path relative to root
            remove_marker: If True, remove .amplified directory

        Returns:
            True if directory was a project and unregistered, False otherwise

        Raises:
            ValueError: If path is invalid
            OSError: If marker removal fails

        Side Effects:
            Removes .amplified directory if remove_marker=True
        """
        try:
            # Validate and resolve path
            dir_path = self._validate_and_resolve_path(relative_path)

            # Check if project
            marker_path = self._get_marker_path(dir_path)
            if not marker_path.exists():
                return False

            # Remove marker if requested
            if remove_marker:
                import shutil

                shutil.rmtree(marker_path)
                logger.info(f"Removed project marker: {relative_path}")

            # Invalidate cache so deleted project no longer appears
            self.invalidate_cache()

            return True

        except Exception as e:
            logger.error(f"Failed to delete project {relative_path}: {e}")
            raise

    def is_project(self, relative_path: str) -> bool:
        """Check if directory is a project.

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

    def _read_agents_file(self, dir_path: Path) -> str | None:
        """Read AGENTS.md from .amplified directory.

        Args:
            dir_path: Absolute directory path

        Returns:
            File content as string, or None if file doesn't exist

        Handles read errors gracefully (logs warning and returns None).
        """
        agents_path = self._get_marker_path(dir_path) / "AGENTS.md"
        if not agents_path.exists():
            return None
        try:
            return agents_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read AGENTS.md from {agents_path}: {e}")
            return None

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

    def _write_agents_file(self, dir_path: Path, agents_content: str) -> None:
        """Write AGENTS.md to filesystem atomically.

        Args:
            dir_path: Absolute directory path
            agents_content: Content to write

        Raises:
            OSError: If write fails

        Implementation:
            Uses tmp + rename pattern for atomic writes.
        """
        agents_path = self._get_marker_path(dir_path) / "AGENTS.md"

        # Ensure .amplified directory exists
        agents_path.parent.mkdir(exist_ok=True)

        # Ensure content ends with newline
        content = agents_content if agents_content.endswith("\n") else agents_content + "\n"

        # Write to tmp file
        tmp_path = agents_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)

            # Rename to AGENTS.md (atomic)
            tmp_path.rename(agents_path)

        except Exception:
            # Cleanup tmp file on failure
            if tmp_path.exists():
                tmp_path.unlink()
            raise
