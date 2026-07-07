"""Project management service."""

import json
import logging
import os
from datetime import UTC
from datetime import datetime
from pathlib import Path
from threading import Lock

from lakehoused.models.projects import Project
from lakehoused.models.projects import ProjectCreate
from lakehoused.models.projects import ProjectUpdate
from lakehoused.storage.paths import get_state_dir

logger = logging.getLogger(__name__)

PROJECT_MARKER_DIR = ".lakehouse"
"""Name of the marker directory that identifies a directory as a lakehouse project."""

REGISTRY_FILENAME = "projects.json"
"""Name of the persistent project registry file (stored in the state directory)."""

# Directories that never contain projects but are huge — pruned during the bootstrap
# / reconcile scan so it stays fast. The scan is not on the request hot path.
SCAN_SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        ".cache",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
)


class ProjectService:
    """Service for managing projects.

    Handles discovery, registration, and metadata management for directories
    containing project marker directories.

    Security-critical: All paths are validated to prevent directory traversal.
    """

    def __init__(self, data_path: Path, max_scan_depth: int = 10) -> None:
        """Initialize with root working directory.

        Args:
            data_path: Root directory (LAKEHOUSED_DATA_PATH)
            max_scan_depth: Maximum directory depth to scan (default: 10)
        """
        self.root = Path(data_path).resolve()

        # Persistent registry: source of truth for list_all() (no filesystem walk).
        # Keyed by relative_path -> Project (without agents_content).
        self._registry: dict[str, Project] = {}
        self._registry_lock = Lock()
        self._registry_path: Path = get_state_dir() / REGISTRY_FILENAME
        self._max_scan_depth: int = max_scan_depth

        # Load the registry now, bootstrapping from a filesystem scan if it's missing.
        self._load_registry()

    def _resolve_default_assistant(self, relative_path: str, provided_profile: str | None) -> str:
        """Resolve default profile for directory.

        Resolution order:
        1. If provided_profile given → use it
        2. Else → find parent project and use its default_assistant
        3. If no parent → use root's default_assistant
        4. Root uses LAKEHOUSED_DEFAULT_ASSISTANT env var (default: foundation/foundation)
        """
        if provided_profile:
            logger.debug(f"Using provided profile: {provided_profile}")
            return provided_profile

        parent_path = self._find_parent_project(relative_path)

        if parent_path:
            parent_metadata = self._read_metadata(parent_path)
            if parent_metadata and "default_assistant" in parent_metadata:
                inherited_profile = parent_metadata["default_assistant"]
                logger.debug(f"Inheriting profile from parent {parent_path}: {inherited_profile}")
                return inherited_profile

        default_assistant = os.getenv("LAKEHOUSED_DEFAULT_ASSISTANT", "foundation/foundation")
        logger.debug(f"Using default profile from environment: {default_assistant}")
        return default_assistant

    def _find_parent_project(self, relative_path: str) -> Path | None:
        """Find nearest parent project.

        Walks up directory tree to find parent with project marker.
        """
        path = Path(relative_path)

        for parent in path.parents:
            if str(parent) == ".":
                root_marker = self.root / PROJECT_MARKER_DIR
                if root_marker.exists() and root_marker.is_dir():
                    return self.root
                return None

            parent_abs = self.root / parent
            parent_marker = parent_abs / PROJECT_MARKER_DIR

            if parent_marker.exists() and parent_marker.is_dir():
                return parent_abs

        root_marker = self.root / PROJECT_MARKER_DIR
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
            - Creates project marker directory if create_marker=True
            - Writes metadata.json with default_assistant
        """
        dir_path = self._validate_and_resolve_path(create_req.relative_path)

        if self.is_project(create_req.relative_path):
            raise ValueError(f"Directory is already a project: {create_req.relative_path}")

        try:
            default_assistant = self._resolve_default_assistant(create_req.relative_path, create_req.default_assistant)

            metadata = create_req.metadata.copy() if create_req.metadata else {}
            metadata["default_assistant"] = default_assistant

            dir_path.mkdir(parents=True, exist_ok=True)

            if create_req.create_marker:
                marker_path = self._get_marker_path(dir_path)
                marker_path.mkdir(exist_ok=True)

            self._write_metadata(dir_path, metadata)

            now = datetime.now(UTC)
            project = Project(
                relative_path=create_req.relative_path,
                default_assistant=metadata.get("default_assistant"),
                metadata=metadata,
                created_at=now,
                last_used_at=None,
                path=str(dir_path),
                is_project=True,
            )

            logger.info(f"Created project: {create_req.relative_path} with profile: {default_assistant}")

            # Register so the new project appears in list_all() without a scan
            self._register(project)

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

            if "default_assistant" not in metadata:
                logger.warning(f"Project {relative_path} missing default_assistant in metadata")

            # Extract default_assistant from metadata for top-level field
            default_assistant = metadata.get("default_assistant")

            # Read AGENTS.md content
            agents_content = self._read_agents_file(dir_path)

            now = datetime.now(UTC)
            return Project(
                relative_path=relative_path,
                default_assistant=default_assistant,
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
        """List all registered projects.

        Args:
            force_refresh: If True, reconcile the registry with the filesystem
                (pruned scan) before returning. Off the request hot path.

        Returns:
            List of Project instances (without agents_content)

        Implementation:
            Reads from the in-memory registry — no filesystem walk. The registry
            is kept current by create/update/delete and persisted to disk.
        """
        if force_refresh:
            self._reconcile_registry()

        with self._registry_lock:
            return list(self._registry.values())

    # --- Registry management ---

    def _load_registry(self) -> None:
        """Load the registry from disk, bootstrapping via a scan if it's missing."""
        if not self._registry_path.exists():
            logger.info("No project registry found; bootstrapping from filesystem scan...")
            self._reconcile_registry()
            return

        try:
            with open(self._registry_path) as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read project registry {self._registry_path}: {e}; rebuilding")
            self._reconcile_registry()
            return

        raw_entries = raw.get("projects", [])
        registry: dict[str, Project] = {}
        for entry in raw_entries:
            try:
                project = Project(**entry)
            except Exception as e:
                logger.warning(f"Skipping malformed registry entry {entry!r}: {e}")
                continue
            # Only trust entries that actually live under this data root. Guards against a
            # registry polluted by a different root (e.g. test /tmp paths) or a stale file
            # left over from a moved data_path.
            if not self._path_under_root(project.path):
                logger.warning(f"Dropping registry entry outside root {self.root}: {project.path}")
                continue
            registry[project.relative_path] = project

        # The file had entries but none belong to this root -> foreign/stale; rebuild by scan.
        if raw_entries and not registry:
            logger.warning(f"Registry has no entries under {self.root}; rebuilding from filesystem scan")
            self._reconcile_registry()
            return

        with self._registry_lock:
            self._registry = registry
        # If we pruned foreign/malformed entries, rewrite the cleaned registry.
        if len(registry) != len(raw_entries):
            self._save_registry()
        logger.info(f"Loaded {len(registry)} projects from registry")

    def _path_under_root(self, path: str) -> bool:
        """True if an absolute project path is within this service's data root."""
        if not path:
            return False
        try:
            return Path(path).resolve().is_relative_to(self.root)
        except (ValueError, OSError):
            return False

    def _save_registry(self) -> None:
        """Persist the registry to disk atomically (tmp + rename)."""
        with self._registry_lock:
            entries = [self._registry_entry(p) for p in self._registry.values()]

        payload = {"projects": entries}
        tmp_path = self._registry_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as f:
                json.dump(payload, f, indent=2, default=str)
            tmp_path.rename(self._registry_path)
        except Exception:
            if tmp_path.exists():
                tmp_path.unlink()
            raise

    @staticmethod
    def _registry_entry(project: Project) -> dict:
        """Serialize a project for the registry (omits agents_content)."""
        return project.model_dump(mode="json", exclude={"agents_content"})

    def _register(self, project: Project) -> None:
        """Add/replace a project in the registry (without agents_content) and persist."""
        entry = project.model_copy(update={"agents_content": None})
        with self._registry_lock:
            self._registry[entry.relative_path] = entry
        self._save_registry()

    def _unregister(self, relative_path: str) -> None:
        """Remove a project from the registry and persist."""
        with self._registry_lock:
            self._registry.pop(relative_path, None)
        self._save_registry()

    def _reconcile_registry(self) -> None:
        """Rebuild the registry from a pruned filesystem scan and persist it."""
        projects = self._scan_filesystem()
        with self._registry_lock:
            self._registry = {p.relative_path: p for p in projects}
        self._save_registry()
        logger.info(f"Reconciled registry: {len(projects)} projects")

    def _scan_filesystem(self) -> list[Project]:
        """Scan the filesystem for projects (bootstrap / reconcile only — not per request).

        Returns:
            List of Project instances (without agents_content)

        Implementation:
            Uses os.walk with in-traversal pruning of heavy directories and
            max_scan_depth, so cost scales with the project tree rather than the
            total file count.
        """
        projects: list[Project] = []
        root_str = str(self.root)

        for dirpath, dirs, _ in os.walk(root_str):
            # Depth of the *children* we're about to descend into.
            depth = dirpath[len(root_str) :].count(os.sep)
            if depth >= self._max_scan_depth:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d not in SCAN_SKIP_DIRS]

            if PROJECT_MARKER_DIR not in dirs and not Path(dirpath, PROJECT_MARKER_DIR).is_dir():
                continue

            dir_path = Path(dirpath)
            try:
                relative_path = str(dir_path.relative_to(self.root))
                metadata = self._read_metadata(dir_path)

                if not metadata:
                    logger.warning(f"Skipping project {relative_path} - no metadata.json")
                    continue

                if "default_assistant" not in metadata:
                    logger.warning(f"Project {relative_path} missing default_assistant")

                projects.append(
                    Project(
                        relative_path=relative_path,
                        default_assistant=metadata.get("default_assistant"),
                        metadata=metadata,
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

            # Merge default_assistant if provided
            if update_req.default_assistant is not None:
                existing_metadata["default_assistant"] = update_req.default_assistant

            # Merge metadata if provided
            if update_req.metadata is not None:
                existing_metadata.update(update_req.metadata)

            # Write merged metadata
            self._write_metadata(dir_path, existing_metadata)

            # Update the registry to reflect the new metadata
            updated = self.get(relative_path)
            if updated:
                self._register(updated)

            return updated

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
            remove_marker: If True, remove project marker directory

        Returns:
            True if directory was a project and unregistered, False otherwise

        Raises:
            ValueError: If path is invalid
            OSError: If marker removal fails

        Side Effects:
            Removes project marker directory if remove_marker=True
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

            # Unregister so the deleted project no longer appears in list_all()
            self._unregister(relative_path)

            return True

        except Exception as e:
            logger.error(f"Failed to delete project {relative_path}: {e}")
            raise

    def is_project(self, relative_path: str) -> bool:
        """Check if directory is a project.

        Args:
            relative_path: Path relative to root

        Returns:
            True if directory contains project marker, False otherwise

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
        """Get project marker directory path.

        Args:
            dir_path: Absolute directory path

        Returns:
            Path to project marker directory
        """
        return dir_path / PROJECT_MARKER_DIR

    def _get_metadata_path(self, dir_path: Path) -> Path:
        """Get metadata.json path.

        Args:
            dir_path: Absolute directory path

        Returns:
            Path to metadata.json file
        """
        return self._get_marker_path(dir_path) / "metadata.json"

    def _read_agents_file(self, dir_path: Path) -> str | None:
        """Read AGENTS.md from project marker directory.

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

        # Ensure project marker directory exists
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

        # Ensure project marker directory exists
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
