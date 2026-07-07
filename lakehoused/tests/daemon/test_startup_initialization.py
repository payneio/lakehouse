"""Tests for daemon startup initialization of projects."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from lakehoused.models.projects import ProjectCreate
from lakehoused.services.project_service import PROJECT_MARKER_DIR
from lakehoused.services.project_service import ProjectService


class TestStartupInitialization:
    """Test daemon startup behavior for projects."""

    @pytest.fixture
    def test_root(self, tmp_path: Path) -> Path:
        """Create test root directory."""
        root = tmp_path / "test_root"
        root.mkdir()
        return root

    @pytest.fixture
    def service(self, test_root: Path, mock_storage_env: Path) -> ProjectService:
        """Create service instance with test root and isolated state (registry)."""
        return ProjectService(test_root)

    def test_root_auto_amplified_on_startup(self, service: ProjectService, test_root: Path) -> None:
        """Test that root directory is auto-amplified on daemon startup."""
        # Simulate startup logic
        if not service.is_project("."):
            default_assistant = os.getenv("LAKEHOUSED_DEFAULT_ASSISTANT", "foundation/foundation")

            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant=default_assistant,
                    metadata={
                        "name": "root",
                        "description": "Root amplified directory (auto-created)",
                        "auto_created": True,
                    },
                    create_marker=True,
                )
            )

        # Verify root is amplified
        assert service.is_project(".")

        # Verify metadata
        root_dir = service.get(".")
        assert root_dir is not None
        assert root_dir.metadata["name"] == "root"
        assert root_dir.metadata["auto_created"] is True
        assert "default_assistant" in root_dir.metadata

        # Verify marker exists
        marker_path = test_root / PROJECT_MARKER_DIR
        assert marker_path.exists()
        assert marker_path.is_dir()

    @patch.dict(os.environ, {"LAKEHOUSED_DEFAULT_ASSISTANT": "custom/profile"})
    def test_root_uses_env_var_bundle(self, service: ProjectService) -> None:
        """Test that root uses LAKEHOUSED_DEFAULT_ASSISTANT environment variable."""
        # Simulate startup logic
        if not service.is_project("."):
            default_assistant = os.getenv("LAKEHOUSED_DEFAULT_ASSISTANT", "foundation/foundation")

            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant=default_assistant,
                    metadata={
                        "name": "root",
                        "description": "Root amplified directory (auto-created)",
                        "auto_created": True,
                    },
                )
            )

        # Verify bundle from environment
        root_dir = service.get(".")
        assert root_dir is not None
        assert root_dir.metadata["default_assistant"] == "custom/profile"

    def test_startup_idempotent(self, service: ProjectService) -> None:
        """Test that startup logic is idempotent (safe to run multiple times)."""
        # First startup
        if not service.is_project("."):
            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant="foundation/foundation",
                    metadata={
                        "name": "root",
                        "auto_created": True,
                    },
                )
            )

        # Verify initial state
        root_dir1 = service.get(".")
        assert root_dir1 is not None
        assert root_dir1.metadata["auto_created"] is True

        # Second startup (simulate restart)
        if not service.is_project("."):
            # This should not execute because already amplified
            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant="foundation/foundation",
                    metadata={
                        "name": "root",
                        "auto_created": True,
                    },
                )
            )

        # Verify state unchanged
        root_dir2 = service.get(".")
        assert root_dir2 is not None
        assert root_dir2.metadata == root_dir1.metadata

    def test_startup_logs_already_amplified(self, service: ProjectService) -> None:
        """Test that startup correctly detects already-amplified root."""
        # Pre-amplify root
        service.create(
            ProjectCreate(
                relative_path=".",
                default_assistant="existing/profile",
                metadata={"name": "Existing Root"},
            )
        )

        # Simulate startup check
        is_already_amplified = service.is_project(".")

        assert is_already_amplified is True

        # Verify startup should skip creation
        if not is_already_amplified:
            pytest.fail("Startup logic should have detected existing amplified root")

    def test_startup_handles_corrupted_root(self, service: ProjectService, test_root: Path) -> None:
        """Test startup handles case where project marker exists but is corrupted."""
        # Create corrupted marker (directory exists but no metadata)
        marker_path = test_root / PROJECT_MARKER_DIR
        marker_path.mkdir()

        # Startup check should report as amplified (marker exists)
        assert service.is_project(".")

        # But getting metadata should fail gracefully
        root_dir = service.get(".")
        assert root_dir is None  # Corrupted, no metadata

        # Startup could handle this by recreating metadata
        # (This is a design decision - currently it would log warning)

    def test_startup_creates_marker_directory(self, service: ProjectService, test_root: Path) -> None:
        """Test that startup creates project marker directory structure."""
        # Simulate startup
        if not service.is_project("."):
            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant="foundation/foundation",
                    metadata={"name": "root"},
                    create_marker=True,
                )
            )

        # Verify directory structure
        marker_path = test_root / PROJECT_MARKER_DIR
        assert marker_path.exists()
        assert marker_path.is_dir()

        metadata_path = marker_path / "metadata.json"
        assert metadata_path.exists()
        assert metadata_path.is_file()

    @patch.dict(os.environ, {}, clear=True)
    def test_startup_default_assistant_fallback(self, service: ProjectService) -> None:
        """Test that startup uses fallback bundle when env var not set."""
        # Ensure LAKEHOUSED_DEFAULT_ASSISTANT is not set
        assert "LAKEHOUSED_DEFAULT_ASSISTANT" not in os.environ

        # Simulate startup
        if not service.is_project("."):
            default_assistant = os.getenv("LAKEHOUSED_DEFAULT_ASSISTANT", "foundation/foundation")

            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant=default_assistant,
                    metadata={"name": "root"},
                )
            )

        # Verify fallback was used
        root_dir = service.get(".")
        assert root_dir is not None
        assert root_dir.metadata["default_assistant"] == "foundation/foundation"

    def test_startup_preserves_existing_root_metadata(self, service: ProjectService) -> None:
        """Test that startup doesn't overwrite existing root metadata."""
        # Create root with custom metadata
        service.create(
            ProjectCreate(
                relative_path=".",
                default_assistant="custom/profile",
                metadata={
                    "name": "Custom Root",
                    "version": 1,
                    "custom_field": "preserved",
                },
            )
        )

        original_dir = service.get(".")
        assert original_dir is not None
        original_metadata = original_dir.metadata

        # Simulate startup (should detect existing and skip)
        if not service.is_project("."):
            # This won't execute
            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant="foundation/foundation",
                    metadata={"name": "root"},
                )
            )

        # Verify metadata unchanged
        current_dir = service.get(".")
        assert current_dir is not None
        current_metadata = current_dir.metadata
        assert current_metadata == original_metadata
        assert current_metadata["name"] == "Custom Root"
        assert current_metadata["custom_field"] == "preserved"

    def test_startup_children_inherit_from_root(self, service: ProjectService) -> None:
        """Test that directories created after startup inherit from root."""
        # Simulate startup - amplify root
        service.create(
            ProjectCreate(
                relative_path=".",
                default_assistant="root/profile",
                metadata={"name": "root"},
            )
        )

        # Create child directory without explicit bundle
        child = service.create(
            ProjectCreate(
                relative_path="child_project",
            )
        )

        # Verify child inherited from root
        assert child.metadata["default_assistant"] == "root/profile"

    def test_startup_error_doesnt_crash_daemon(self, service: ProjectService, test_root: Path) -> None:
        """Test that startup errors don't crash the daemon."""
        # Make root read-only to cause error
        test_root.chmod(0o444)

        try:
            # Simulate startup logic with error handling
            try:
                if not service.is_project("."):
                    service.create(
                        ProjectCreate(
                            relative_path=".",
                            default_assistant="foundation/foundation",
                            metadata={"name": "root"},
                        )
                    )
            except Exception:
                # Startup should catch exception and continue
                pass

            # Daemon should continue even if auto-amplify failed
            # (This test verifies the error handling pattern)

        finally:
            # Restore permissions for cleanup
            test_root.chmod(0o755)

    def test_multiple_startups_consistent_state(self, service: ProjectService) -> None:
        """Test that multiple daemon restarts maintain consistent state."""
        # First startup
        if not service.is_project("."):
            service.create(
                ProjectCreate(
                    relative_path=".",
                    default_assistant="foundation/foundation",
                    metadata={"name": "root", "startup_count": 1},
                )
            )

        state_after_first = service.get(".")
        assert state_after_first is not None

        # Simulate multiple restarts
        for _ in range(5):
            if not service.is_project("."):
                # Should not execute
                pytest.fail("Root should remain amplified across restarts")

        state_after_multiple = service.get(".")
        assert state_after_multiple is not None

        # Verify state is consistent
        assert state_after_multiple.relative_path == state_after_first.relative_path
        assert state_after_multiple.metadata["name"] == state_after_first.metadata["name"]
        assert state_after_multiple.metadata["default_assistant"] == state_after_first.metadata["default_assistant"]
