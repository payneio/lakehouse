"""Unit tests for ProjectService."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from lakehoused.models.projects import ProjectCreate
from lakehoused.models.projects import ProjectUpdate
from lakehoused.services.project_service import ProjectService


class TestProjectService:
    """Tests for ProjectService."""

    @pytest.fixture
    def test_root(self, tmp_path: Path) -> Path:
        """Create test root directory."""
        root = tmp_path / "test_root"
        root.mkdir()
        return root

    @pytest.fixture
    def service(self, test_root: Path) -> ProjectService:
        """Create service instance with test root."""
        return ProjectService(test_root)

    # --- Security Tests (Critical Priority) ---

    def test_rejects_absolute_paths(self, service: ProjectService) -> None:
        """Test that absolute paths are rejected during validation."""
        # Test service-level validation rejects absolute paths
        with pytest.raises(ValueError, match="Path must be relative"):
            service._validate_and_resolve_path("/etc/passwd")

        # Also test through create (which also validates)
        create_req = ProjectCreate(relative_path="/absolute/path")
        with pytest.raises(ValueError, match="Path must be relative"):
            service.create(create_req)

    def test_rejects_parent_traversal(self, service: ProjectService) -> None:
        """Test that paths with '..' are rejected."""
        # Attempt various parent traversal patterns
        patterns = ["../../etc/passwd", "../sibling", "subdir/../../escape"]

        for pattern in patterns:
            with pytest.raises(ValueError, match="cannot contain '\\.\\.'"):
                service._validate_and_resolve_path(pattern)

        # Also test through create method
        create_req = ProjectCreate(relative_path="../../escape")
        with pytest.raises(ValueError, match="cannot contain '\\.\\.'"):
            service.create(create_req)

    def test_rejects_symlink_escape(self, service: ProjectService, test_root: Path, tmp_path: Path) -> None:
        """Test that symlinks pointing outside root are rejected."""
        # Create directory outside root
        outside = tmp_path / "outside"
        outside.mkdir()

        # Create symlink inside root pointing outside
        symlink = test_root / "malicious_link"
        symlink.symlink_to(outside)

        # Attempt to validate path through symlink
        with pytest.raises(ValueError, match="Path escapes root"):
            service._validate_and_resolve_path("malicious_link")

    def test_validates_within_root(self, service: ProjectService, test_root: Path) -> None:
        """Test that valid relative paths are accepted and resolved correctly."""
        # Valid paths
        valid_paths = [
            "project",
            "sub/dir",
            "deeply/nested/structure",
            "project_123",
            "project-with-dashes",
            "project.with.dots",
        ]

        for path in valid_paths:
            resolved = service._validate_and_resolve_path(path)
            assert resolved.is_relative_to(test_root)
            assert str(resolved).startswith(str(test_root))

    # --- CRUD Tests ---

    def test_create_directory_basic(self, service: ProjectService, test_root: Path) -> None:
        """Test creating project with basic parameters."""
        create_req = ProjectCreate(relative_path="test_project")

        result = service.create(create_req)

        # Verify result
        assert result.relative_path == "test_project"
        assert "default_bundle" in result.metadata
        assert result.created_at is not None
        assert result.last_used_at is None

        # Verify filesystem
        assert (test_root / "test_project").exists()
        assert (test_root / "test_project" / ".amplified").exists()
        assert (test_root / "test_project" / ".amplified" / "metadata.json").exists()

    def test_create_with_explicit_profile(self, service: ProjectService) -> None:
        """Test creating directory with explicit default_bundle."""
        create_req = ProjectCreate(
            relative_path="custom_project",
            default_bundle="developer-expertise/dev",
        )

        result = service.create(create_req)

        assert result.metadata["default_bundle"] == "developer-expertise/dev"

    def test_create_with_custom_metadata(self, service: ProjectService) -> None:
        """Test creating directory with additional metadata."""
        create_req = ProjectCreate(
            relative_path="project_with_metadata",
            metadata={
                "name": "My Project",
                "description": "Test project",
                "tags": ["test", "example"],
            },
        )

        result = service.create(create_req)

        assert result.metadata["name"] == "My Project"
        assert result.metadata["description"] == "Test project"
        assert result.metadata["tags"] == ["test", "example"]
        assert "default_bundle" in result.metadata  # Should still be set

    def test_create_with_explicit_marker_flag(self, service: ProjectService, test_root: Path) -> None:
        """Test that create_marker flag controls marker directory creation."""
        # Test with create_marker=True (default behavior - creates marker)
        create_req1 = ProjectCreate(
            relative_path="with_marker",
            create_marker=True,
        )
        result1 = service.create(create_req1)

        assert result1 is not None
        assert (test_root / "with_marker" / ".amplified").exists()
        assert (test_root / "with_marker" / ".amplified" / "metadata.json").exists()

    def test_create_already_exists_raises_error(self, service: ProjectService, test_root: Path) -> None:
        """Test that creating already-project raises ValueError."""
        # Create first time
        create_req = ProjectCreate(relative_path="duplicate")
        service.create(create_req)

        # Attempt to create again
        with pytest.raises(ValueError, match="already a project"):
            service.create(create_req)

    def test_get_existing_directory(self, service: ProjectService) -> None:
        """Test getting existing project."""
        # Create directory
        create_req = ProjectCreate(
            relative_path="to_retrieve",
            metadata={"name": "Retrievable"},
        )
        created = service.create(create_req)

        # Retrieve it
        result = service.get("to_retrieve")

        assert result is not None
        assert result.relative_path == "to_retrieve"
        assert result.metadata["name"] == "Retrievable"
        assert result.metadata["default_bundle"] == created.metadata["default_bundle"]

    def test_get_nonexistent_returns_none(self, service: ProjectService) -> None:
        """Test that getting non-existent directory returns None."""
        result = service.get("nonexistent")

        assert result is None

    def test_get_non_amplified_returns_none(self, service: ProjectService, test_root: Path) -> None:
        """Test that getting directory without .amplified marker returns None."""
        # Create directory without amplified marker
        non_amplified = test_root / "regular_dir"
        non_amplified.mkdir()

        result = service.get("regular_dir")

        assert result is None

    def test_list_all_discovers_multiple(self, service: ProjectService) -> None:
        """Test that list_all discovers all projects."""
        # Create multiple directories
        dirs = ["project1", "project2", "nested/project3"]
        for path in dirs:
            create_req = ProjectCreate(relative_path=path)
            service.create(create_req)

        # List all
        results = service.list_all()

        assert len(results) == 3
        paths = {r.relative_path for r in results}
        assert paths == {"project1", "project2", "nested/project3"}

    def test_list_all_empty_root(self, service: ProjectService) -> None:
        """Test that list_all returns empty list when no projects exist."""
        results = service.list_all()

        assert results == []

    def test_update_metadata_merges(self, service: ProjectService, test_root: Path) -> None:
        """Test that update merges new metadata with existing."""
        # Create directory with initial metadata
        create_req = ProjectCreate(
            relative_path="to_update",
            metadata={"name": "Original", "version": 1},
        )
        service.create(create_req)

        # Update with new metadata
        update_req = ProjectUpdate(
            metadata={
                "name": "Updated",
                "description": "New description",
                "default_bundle": "foundation/base",
            }
        )
        result = service.update("to_update", update_req)

        assert result is not None
        assert result.metadata["name"] == "Updated"
        assert result.metadata["description"] == "New description"
        assert result.metadata["default_bundle"] == "foundation/base"

    def test_update_nonexistent_returns_none(self, service: ProjectService) -> None:
        """Test that updating non-existent directory returns None."""
        update_req = ProjectUpdate(metadata={"key": "value"})
        result = service.update("nonexistent", update_req)

        assert result is None

    def test_delete_removes_marker(self, service: ProjectService, test_root: Path) -> None:
        """Test that delete removes .amplified marker."""
        # Create directory
        create_req = ProjectCreate(relative_path="to_delete")
        service.create(create_req)

        marker_path = test_root / "to_delete" / ".amplified"
        assert marker_path.exists()

        # Delete with marker removal
        result = service.delete("to_delete", remove_marker=True)

        assert result is True
        assert not marker_path.exists()

    def test_delete_without_marker_removal(self, service: ProjectService, test_root: Path) -> None:
        """Test that delete without remove_marker keeps marker."""
        # Create directory
        create_req = ProjectCreate(relative_path="to_keep_marker")
        service.create(create_req)

        marker_path = test_root / "to_keep_marker" / ".amplified"
        assert marker_path.exists()

        # Delete without marker removal (default)
        result = service.delete("to_keep_marker", remove_marker=False)

        assert result is True
        assert marker_path.exists()  # Marker still exists

    def test_delete_nonexistent_returns_false(self, service: ProjectService) -> None:
        """Test that deleting non-existent directory returns False."""
        result = service.delete("nonexistent")

        assert result is False

    def test_is_project_true(self, service: ProjectService) -> None:
        """Test is_project returns True for project."""
        create_req = ProjectCreate(relative_path="check_amplified")
        service.create(create_req)

        assert service.is_project("check_amplified") is True

    def test_is_project_false(self, service: ProjectService, test_root: Path) -> None:
        """Test is_project returns False for non-project."""
        # Create regular directory
        regular = test_root / "regular"
        regular.mkdir()

        assert service.is_project("regular") is False

    def test_is_project_nonexistent(self, service: ProjectService) -> None:
        """Test is_project returns False for non-existent directory."""
        assert service.is_project("nonexistent") is False

    def test_is_project_invalid_path(self, service: ProjectService) -> None:
        """Test is_project returns False for invalid paths."""
        assert service.is_project("../../escape") is False
        assert service.is_project("/absolute") is False

    # --- Profile Inheritance Tests ---

    def test_explicit_profile_used_when_provided(self, service: ProjectService) -> None:
        """Test that explicit profile is used when provided."""
        create_req = ProjectCreate(
            relative_path="explicit",
            default_bundle="custom/profile",
        )

        result = service.create(create_req)

        assert result.metadata["default_bundle"] == "custom/profile"

    def test_inherits_from_parent_directory(self, service: ProjectService, test_root: Path) -> None:
        """Test that child inherits default_bundle from parent."""
        # Create parent with explicit bundle
        parent_req = ProjectCreate(
            relative_path="parent",
            default_bundle="parent/profile",
        )
        service.create(parent_req)

        # Create child without explicit bundle
        child_req = ProjectCreate(relative_path="parent/child")
        child = service.create(child_req)

        assert child.metadata["default_bundle"] == "parent/profile"

    def test_inherits_from_root_when_no_parent(self, service: ProjectService, test_root: Path) -> None:
        """Test that directory inherits from root when no parent amplified."""
        # Amplify root first
        root_req = ProjectCreate(
            relative_path=".",
            default_bundle="root/profile",
        )
        service.create(root_req)

        # Create directory without explicit bundle (no intermediate parent)
        child_req = ProjectCreate(relative_path="orphan")
        child = service.create(child_req)

        assert child.metadata["default_bundle"] == "root/profile"

    @patch.dict(os.environ, {"AMPLIFIERD_DEFAULT_BUNDLE": "env/profile"})
    def test_root_uses_env_var_default(self, service: ProjectService) -> None:
        """Test that root uses environment variable for default profile."""
        create_req = ProjectCreate(relative_path="project")

        result = service.create(create_req)

        assert result.metadata["default_bundle"] == "env/profile"

    def test_nested_inheritance_chain(self, service: ProjectService) -> None:
        """Test inheritance through multiple levels."""
        # Create grandparent
        grandparent_req = ProjectCreate(
            relative_path="grandparent",
            default_bundle="grandparent/profile",
        )
        service.create(grandparent_req)

        # Create parent (inherits from grandparent)
        parent_req = ProjectCreate(relative_path="grandparent/parent")
        parent = service.create(parent_req)
        assert parent.metadata["default_bundle"] == "grandparent/profile"

        # Create child (inherits from parent)
        child_req = ProjectCreate(relative_path="grandparent/parent/child")
        child = service.create(child_req)
        assert child.metadata["default_bundle"] == "grandparent/profile"

        # Now update parent to have different profile
        parent_update = ProjectUpdate(metadata={"default_bundle": "parent/profile"})
        service.update("grandparent/parent", parent_update)

        # Create new child (should inherit parent's updated profile)
        child2_req = ProjectCreate(relative_path="grandparent/parent/child2")
        child2 = service.create(child2_req)
        assert child2.metadata["default_bundle"] == "parent/profile"

    # --- Edge Cases ---

    def test_nested_directories_independent(self, service: ProjectService) -> None:
        """Test that nested projects are independent."""
        # Create parent
        parent_req = ProjectCreate(
            relative_path="parent",
            metadata={"name": "Parent"},
        )
        service.create(parent_req)

        # Create child
        child_req = ProjectCreate(
            relative_path="parent/child",
            metadata={"name": "Child"},
        )
        service.create(child_req)

        # List all - should find both
        results = service.list_all()
        assert len(results) == 2

        # Get each independently
        parent = service.get("parent")
        child = service.get("parent/child")

        assert parent is not None
        assert child is not None
        assert parent.metadata["name"] == "Parent"
        assert child.metadata["name"] == "Child"

    def test_metadata_file_corruption_handled(self, service: ProjectService, test_root: Path) -> None:
        """Test that corrupted metadata.json is handled gracefully."""
        # Create directory
        create_req = ProjectCreate(relative_path="corrupted")
        service.create(create_req)

        # Corrupt metadata file
        metadata_path = test_root / "corrupted" / ".amplified" / "metadata.json"
        metadata_path.write_text("{ invalid json }")

        # Attempt to get - should return None due to JSON error
        result = service.get("corrupted")

        assert result is None

    def test_missing_default_bundle_in_metadata(self, service: ProjectService, test_root: Path) -> None:
        """Test handling of project missing default_bundle."""
        # Create directory manually without default_bundle
        marker_path = test_root / "no_profile" / ".amplified"
        marker_path.mkdir(parents=True)

        metadata_path = marker_path / "metadata.json"
        metadata_path.write_text(json.dumps({"name": "No Profile"}))

        # Get should succeed but log warning
        result = service.get("no_profile")

        assert result is not None
        assert result.metadata["name"] == "No Profile"
        assert "default_bundle" not in result.metadata

    def test_special_characters_in_path(self, service: ProjectService) -> None:
        """Test paths with special but valid characters."""
        valid_special = [
            "project_123",
            "project-with-dashes",
            "project.with.dots",
            "PROJECT_CAPS",
            "project with spaces",  # Spaces are valid in filesystem paths
        ]

        for path in valid_special:
            create_req = ProjectCreate(relative_path=path)
            result = service.create(create_req)

            assert result is not None
            assert service.is_project(path) is True

    def test_empty_relative_path(self, service: ProjectService) -> None:
        """Test handling of empty relative path."""
        # Empty path should be treated as current directory (".")
        create_req = ProjectCreate(relative_path=".")
        result = service.create(create_req)

        assert result is not None
        # Relative path might be normalized to "." or ""
        assert result.relative_path in [".", ""]

    def test_concurrent_operations_same_directory(self, service: ProjectService) -> None:
        """Test that service handles operations on same directory."""
        # Create directory
        create_req = ProjectCreate(relative_path="concurrent")
        service.create(create_req)

        # Multiple reads should work
        result1 = service.get("concurrent")
        result2 = service.get("concurrent")

        assert result1 is not None
        assert result2 is not None
        assert result1.relative_path == result2.relative_path

        # Update then read
        update_req = ProjectUpdate(metadata={"version": 2})
        service.update("concurrent", update_req)

        result3 = service.get("concurrent")
        assert result3 is not None
        assert result3.metadata["version"] == 2

    def test_list_all_ignores_non_directory_markers(self, service: ProjectService, test_root: Path) -> None:
        """Test that list_all ignores .amplified files (not directories)."""
        # Create valid project
        create_req = ProjectCreate(relative_path="valid")
        service.create(create_req)

        # Create .amplified as file (invalid)
        invalid_marker = test_root / "invalid" / ".amplified"
        invalid_marker.parent.mkdir()
        invalid_marker.touch()  # Create as file, not directory

        # List all - should only find valid one
        results = service.list_all()

        assert len(results) == 1
        assert results[0].relative_path == "valid"

    def test_update_merges_metadata(self, service: ProjectService) -> None:
        """Test that update merges metadata (preserves existing fields)."""
        # Create with metadata
        create_req = ProjectCreate(
            relative_path="preserve",
            metadata={"field1": "value1", "field2": "value2"},
        )
        service.create(create_req)

        # Update with new metadata (merging with existing)
        update_req = ProjectUpdate(
            metadata={"field1": "updated", "field3": "value3", "default_bundle": "foundation/base"}
        )
        result = service.update("preserve", update_req)

        assert result is not None
        # New metadata should merge with existing (not replace)
        assert result.metadata["field1"] == "updated"  # Updated value
        assert result.metadata["field2"] == "value2"  # Preserved from original
        assert result.metadata["field3"] == "value3"  # New field added

    def test_find_parent_project(self, service: ProjectService) -> None:
        """Test _find_parent_project helper."""
        # Create grandparent and parent
        service.create(ProjectCreate(relative_path="grandparent"))
        service.create(ProjectCreate(relative_path="grandparent/parent"))

        # Find parent for deep child (not yet amplified)
        parent = service._find_parent_project("grandparent/parent/child")

        assert parent is not None
        assert parent.name == "parent"

        # Find parent for mid-level child
        parent2 = service._find_parent_project("grandparent/not_amplified")

        assert parent2 is not None
        assert parent2.name == "grandparent"

    def test_atomic_metadata_write(self, service: ProjectService, test_root: Path) -> None:
        """Test that metadata writes are atomic (tmp + rename pattern)."""
        # Create directory
        create_req = ProjectCreate(relative_path="atomic")
        service.create(create_req)

        metadata_path = test_root / "atomic" / ".amplified" / "metadata.json"
        tmp_path = metadata_path.with_suffix(".tmp")

        # Update metadata
        update_req = ProjectUpdate(metadata={"test": "atomic", "default_bundle": "foundation/base"})
        service.update("atomic", update_req)

        # Verify tmp file doesn't exist after successful write
        assert not tmp_path.exists()
        # Verify metadata file exists and has correct content
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)
        assert metadata["test"] == "atomic"

    def test_agents_content_loaded_when_present(self, service: ProjectService, test_root: Path) -> None:
        """Test that AGENTS.md content is loaded when file exists."""
        # Create directory
        create_req = ProjectCreate(relative_path="with_agents")
        service.create(create_req)

        # Add AGENTS.md file
        agents_path = test_root / "with_agents" / ".amplified" / "AGENTS.md"
        agents_content = "# Test AGENTS.md\n\nThis is test content."
        agents_path.write_text(agents_content, encoding="utf-8")

        # Get directory and verify agents_content is loaded
        result = service.get("with_agents")

        assert result is not None
        assert result.agents_content == agents_content

    def test_agents_content_none_when_missing(self, service: ProjectService) -> None:
        """Test that agents_content is None when AGENTS.md doesn't exist."""
        # Create directory without AGENTS.md
        create_req = ProjectCreate(relative_path="no_agents")
        service.create(create_req)

        # Get directory and verify agents_content is None
        result = service.get("no_agents")

        assert result is not None
        assert result.agents_content is None

    def test_agents_content_none_on_read_error(
        self, service: ProjectService, test_root: Path
    ) -> None:
        """Test that agents_content is None when AGENTS.md read fails."""
        # Create directory
        create_req = ProjectCreate(relative_path="broken_agents")
        service.create(create_req)

        # Create AGENTS.md with no read permissions
        agents_path = test_root / "broken_agents" / ".amplified" / "AGENTS.md"
        agents_path.write_text("content", encoding="utf-8")
        agents_path.chmod(0o000)  # No permissions

        try:
            # Get directory - should handle read error gracefully
            result = service.get("broken_agents")

            assert result is not None
            assert result.agents_content is None  # Should be None due to read error
        finally:
            # Restore permissions for cleanup
            agents_path.chmod(0o644)
