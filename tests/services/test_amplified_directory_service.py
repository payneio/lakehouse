"""Unit tests for AmplifiedDirectoryService."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from amplifierd.models.amplified_directories import AmplifiedDirectoryCreate
from amplifierd.models.amplified_directories import AmplifiedDirectoryUpdate
from amplifierd.services.amplified_directory_service import AmplifiedDirectoryService


class TestAmplifiedDirectoryService:
    """Tests for AmplifiedDirectoryService."""

    @pytest.fixture
    def test_root(self, tmp_path: Path) -> Path:
        """Create test root directory."""
        root = tmp_path / "test_root"
        root.mkdir()
        return root

    @pytest.fixture
    def service(self, test_root: Path) -> AmplifiedDirectoryService:
        """Create service instance with test root."""
        return AmplifiedDirectoryService(test_root)

    # --- Security Tests (Critical Priority) ---

    def test_rejects_absolute_paths(self, service: AmplifiedDirectoryService) -> None:
        """Test that absolute paths are rejected during validation."""
        # Test service-level validation rejects absolute paths
        with pytest.raises(ValueError, match="Path must be relative"):
            service._validate_and_resolve_path("/etc/passwd")

        # Also test through create (which also validates)
        create_req = AmplifiedDirectoryCreate(relative_path="/absolute/path")
        with pytest.raises(ValueError, match="Path must be relative"):
            service.create(create_req)

    def test_rejects_parent_traversal(self, service: AmplifiedDirectoryService) -> None:
        """Test that paths with '..' are rejected."""
        # Attempt various parent traversal patterns
        patterns = ["../../etc/passwd", "../sibling", "subdir/../../escape"]

        for pattern in patterns:
            with pytest.raises(ValueError, match="cannot contain '\\.\\.'"):
                service._validate_and_resolve_path(pattern)

        # Also test through create method
        create_req = AmplifiedDirectoryCreate(relative_path="../../escape")
        with pytest.raises(ValueError, match="cannot contain '\\.\\.'"):
            service.create(create_req)

    def test_rejects_symlink_escape(self, service: AmplifiedDirectoryService, test_root: Path, tmp_path: Path) -> None:
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

    def test_validates_within_root(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
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

    def test_create_directory_basic(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test creating amplified directory with basic parameters."""
        create_req = AmplifiedDirectoryCreate(relative_path="test_project")

        result = service.create(create_req)

        # Verify result
        assert result.relative_path == "test_project"
        assert "default_profile" in result.metadata
        assert result.created_at is not None
        assert result.last_used_at is None

        # Verify filesystem
        assert (test_root / "test_project").exists()
        assert (test_root / "test_project" / ".amplified").exists()
        assert (test_root / "test_project" / ".amplified" / "metadata.json").exists()

    def test_create_with_explicit_profile(self, service: AmplifiedDirectoryService) -> None:
        """Test creating directory with explicit default_profile."""
        create_req = AmplifiedDirectoryCreate(
            relative_path="custom_project",
            default_profile="developer-expertise/dev",
        )

        result = service.create(create_req)

        assert result.metadata["default_profile"] == "developer-expertise/dev"

    def test_create_with_custom_metadata(self, service: AmplifiedDirectoryService) -> None:
        """Test creating directory with additional metadata."""
        create_req = AmplifiedDirectoryCreate(
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
        assert "default_profile" in result.metadata  # Should still be set

    def test_create_with_explicit_marker_flag(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that create_marker flag controls marker directory creation."""
        # Test with create_marker=True (default behavior - creates marker)
        create_req1 = AmplifiedDirectoryCreate(
            relative_path="with_marker",
            create_marker=True,
        )
        result1 = service.create(create_req1)

        assert result1 is not None
        assert (test_root / "with_marker" / ".amplified").exists()
        assert (test_root / "with_marker" / ".amplified" / "metadata.json").exists()

    def test_create_already_exists_raises_error(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that creating already-amplified directory raises ValueError."""
        # Create first time
        create_req = AmplifiedDirectoryCreate(relative_path="duplicate")
        service.create(create_req)

        # Attempt to create again
        with pytest.raises(ValueError, match="already amplified"):
            service.create(create_req)

    def test_get_existing_directory(self, service: AmplifiedDirectoryService) -> None:
        """Test getting existing amplified directory."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(
            relative_path="to_retrieve",
            metadata={"name": "Retrievable"},
        )
        created = service.create(create_req)

        # Retrieve it
        result = service.get("to_retrieve")

        assert result is not None
        assert result.relative_path == "to_retrieve"
        assert result.metadata["name"] == "Retrievable"
        assert result.metadata["default_profile"] == created.metadata["default_profile"]

    def test_get_nonexistent_returns_none(self, service: AmplifiedDirectoryService) -> None:
        """Test that getting non-existent directory returns None."""
        result = service.get("nonexistent")

        assert result is None

    def test_get_non_amplified_returns_none(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that getting directory without .amplified marker returns None."""
        # Create directory without amplified marker
        non_amplified = test_root / "regular_dir"
        non_amplified.mkdir()

        result = service.get("regular_dir")

        assert result is None

    def test_list_all_discovers_multiple(self, service: AmplifiedDirectoryService) -> None:
        """Test that list_all discovers all amplified directories."""
        # Create multiple directories
        dirs = ["project1", "project2", "nested/project3"]
        for path in dirs:
            create_req = AmplifiedDirectoryCreate(relative_path=path)
            service.create(create_req)

        # List all
        results = service.list_all()

        assert len(results) == 3
        paths = {r.relative_path for r in results}
        assert paths == {"project1", "project2", "nested/project3"}

    def test_list_all_empty_root(self, service: AmplifiedDirectoryService) -> None:
        """Test that list_all returns empty list when no amplified directories exist."""
        results = service.list_all()

        assert results == []

    def test_update_metadata_merges(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that update merges new metadata with existing."""
        # Create directory with initial metadata
        create_req = AmplifiedDirectoryCreate(
            relative_path="to_update",
            metadata={"name": "Original", "version": 1},
        )
        service.create(create_req)

        # Update with new metadata
        update_req = AmplifiedDirectoryUpdate(
            metadata={
                "name": "Updated",
                "description": "New description",
                "default_profile": "foundation/base",
            }
        )
        result = service.update("to_update", update_req)

        assert result is not None
        assert result.metadata["name"] == "Updated"
        assert result.metadata["description"] == "New description"
        assert result.metadata["default_profile"] == "foundation/base"

    def test_update_nonexistent_returns_none(self, service: AmplifiedDirectoryService) -> None:
        """Test that updating non-existent directory returns None."""
        update_req = AmplifiedDirectoryUpdate(metadata={"key": "value"})
        result = service.update("nonexistent", update_req)

        assert result is None

    def test_delete_removes_marker(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that delete removes .amplified marker."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(relative_path="to_delete")
        service.create(create_req)

        marker_path = test_root / "to_delete" / ".amplified"
        assert marker_path.exists()

        # Delete with marker removal
        result = service.delete("to_delete", remove_marker=True)

        assert result is True
        assert not marker_path.exists()

    def test_delete_without_marker_removal(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that delete without remove_marker keeps marker."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(relative_path="to_keep_marker")
        service.create(create_req)

        marker_path = test_root / "to_keep_marker" / ".amplified"
        assert marker_path.exists()

        # Delete without marker removal (default)
        result = service.delete("to_keep_marker", remove_marker=False)

        assert result is True
        assert marker_path.exists()  # Marker still exists

    def test_delete_nonexistent_returns_false(self, service: AmplifiedDirectoryService) -> None:
        """Test that deleting non-existent directory returns False."""
        result = service.delete("nonexistent")

        assert result is False

    def test_is_amplified_true(self, service: AmplifiedDirectoryService) -> None:
        """Test is_amplified returns True for amplified directory."""
        create_req = AmplifiedDirectoryCreate(relative_path="check_amplified")
        service.create(create_req)

        assert service.is_amplified("check_amplified") is True

    def test_is_amplified_false(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test is_amplified returns False for non-amplified directory."""
        # Create regular directory
        regular = test_root / "regular"
        regular.mkdir()

        assert service.is_amplified("regular") is False

    def test_is_amplified_nonexistent(self, service: AmplifiedDirectoryService) -> None:
        """Test is_amplified returns False for non-existent directory."""
        assert service.is_amplified("nonexistent") is False

    def test_is_amplified_invalid_path(self, service: AmplifiedDirectoryService) -> None:
        """Test is_amplified returns False for invalid paths."""
        assert service.is_amplified("../../escape") is False
        assert service.is_amplified("/absolute") is False

    # --- Profile Inheritance Tests ---

    def test_explicit_profile_used_when_provided(self, service: AmplifiedDirectoryService) -> None:
        """Test that explicit profile is used when provided."""
        create_req = AmplifiedDirectoryCreate(
            relative_path="explicit",
            default_profile="custom/profile",
        )

        result = service.create(create_req)

        assert result.metadata["default_profile"] == "custom/profile"

    def test_inherits_from_parent_directory(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that child inherits default_profile from parent."""
        # Create parent with explicit profile
        parent_req = AmplifiedDirectoryCreate(
            relative_path="parent",
            default_profile="parent/profile",
        )
        service.create(parent_req)

        # Create child without explicit profile
        child_req = AmplifiedDirectoryCreate(relative_path="parent/child")
        child = service.create(child_req)

        assert child.metadata["default_profile"] == "parent/profile"

    def test_inherits_from_root_when_no_parent(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that directory inherits from root when no parent amplified."""
        # Amplify root first
        root_req = AmplifiedDirectoryCreate(
            relative_path=".",
            default_profile="root/profile",
        )
        service.create(root_req)

        # Create directory without explicit profile (no intermediate parent)
        child_req = AmplifiedDirectoryCreate(relative_path="orphan")
        child = service.create(child_req)

        assert child.metadata["default_profile"] == "root/profile"

    @patch.dict(os.environ, {"AMPLIFIERD_DEFAULT_PROFILE": "env/profile"})
    def test_root_uses_env_var_default(self, service: AmplifiedDirectoryService) -> None:
        """Test that root uses environment variable for default profile."""
        create_req = AmplifiedDirectoryCreate(relative_path="project")

        result = service.create(create_req)

        assert result.metadata["default_profile"] == "env/profile"

    def test_nested_inheritance_chain(self, service: AmplifiedDirectoryService) -> None:
        """Test inheritance through multiple levels."""
        # Create grandparent
        grandparent_req = AmplifiedDirectoryCreate(
            relative_path="grandparent",
            default_profile="grandparent/profile",
        )
        service.create(grandparent_req)

        # Create parent (inherits from grandparent)
        parent_req = AmplifiedDirectoryCreate(relative_path="grandparent/parent")
        parent = service.create(parent_req)
        assert parent.metadata["default_profile"] == "grandparent/profile"

        # Create child (inherits from parent)
        child_req = AmplifiedDirectoryCreate(relative_path="grandparent/parent/child")
        child = service.create(child_req)
        assert child.metadata["default_profile"] == "grandparent/profile"

        # Now update parent to have different profile
        parent_update = AmplifiedDirectoryUpdate(metadata={"default_profile": "parent/profile"})
        service.update("grandparent/parent", parent_update)

        # Create new child (should inherit parent's updated profile)
        child2_req = AmplifiedDirectoryCreate(relative_path="grandparent/parent/child2")
        child2 = service.create(child2_req)
        assert child2.metadata["default_profile"] == "parent/profile"

    # --- Edge Cases ---

    def test_nested_directories_independent(self, service: AmplifiedDirectoryService) -> None:
        """Test that nested amplified directories are independent."""
        # Create parent
        parent_req = AmplifiedDirectoryCreate(
            relative_path="parent",
            metadata={"name": "Parent"},
        )
        service.create(parent_req)

        # Create child
        child_req = AmplifiedDirectoryCreate(
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

    def test_metadata_file_corruption_handled(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that corrupted metadata.json is handled gracefully."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(relative_path="corrupted")
        service.create(create_req)

        # Corrupt metadata file
        metadata_path = test_root / "corrupted" / ".amplified" / "metadata.json"
        metadata_path.write_text("{ invalid json }")

        # Attempt to get - should return None due to JSON error
        result = service.get("corrupted")

        assert result is None

    def test_missing_default_profile_in_metadata(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test handling of amplified directory missing default_profile."""
        # Create directory manually without default_profile
        marker_path = test_root / "no_profile" / ".amplified"
        marker_path.mkdir(parents=True)

        metadata_path = marker_path / "metadata.json"
        metadata_path.write_text(json.dumps({"name": "No Profile"}))

        # Get should succeed but log warning
        result = service.get("no_profile")

        assert result is not None
        assert result.metadata["name"] == "No Profile"
        assert "default_profile" not in result.metadata

    def test_special_characters_in_path(self, service: AmplifiedDirectoryService) -> None:
        """Test paths with special but valid characters."""
        valid_special = [
            "project_123",
            "project-with-dashes",
            "project.with.dots",
            "PROJECT_CAPS",
            "project with spaces",  # Spaces are valid in filesystem paths
        ]

        for path in valid_special:
            create_req = AmplifiedDirectoryCreate(relative_path=path)
            result = service.create(create_req)

            assert result is not None
            assert service.is_amplified(path) is True

    def test_empty_relative_path(self, service: AmplifiedDirectoryService) -> None:
        """Test handling of empty relative path."""
        # Empty path should be treated as current directory (".")
        create_req = AmplifiedDirectoryCreate(relative_path=".")
        result = service.create(create_req)

        assert result is not None
        # Relative path might be normalized to "." or ""
        assert result.relative_path in [".", ""]

    def test_concurrent_operations_same_directory(self, service: AmplifiedDirectoryService) -> None:
        """Test that service handles operations on same directory."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(relative_path="concurrent")
        service.create(create_req)

        # Multiple reads should work
        result1 = service.get("concurrent")
        result2 = service.get("concurrent")

        assert result1 is not None
        assert result2 is not None
        assert result1.relative_path == result2.relative_path

        # Update then read
        update_req = AmplifiedDirectoryUpdate(metadata={"version": 2})
        service.update("concurrent", update_req)

        result3 = service.get("concurrent")
        assert result3 is not None
        assert result3.metadata["version"] == 2

    def test_list_all_ignores_non_directory_markers(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that list_all ignores .amplified files (not directories)."""
        # Create valid amplified directory
        create_req = AmplifiedDirectoryCreate(relative_path="valid")
        service.create(create_req)

        # Create .amplified as file (invalid)
        invalid_marker = test_root / "invalid" / ".amplified"
        invalid_marker.parent.mkdir()
        invalid_marker.touch()  # Create as file, not directory

        # List all - should only find valid one
        results = service.list_all()

        assert len(results) == 1
        assert results[0].relative_path == "valid"

    def test_update_merges_metadata(self, service: AmplifiedDirectoryService) -> None:
        """Test that update merges metadata (preserves existing fields)."""
        # Create with metadata
        create_req = AmplifiedDirectoryCreate(
            relative_path="preserve",
            metadata={"field1": "value1", "field2": "value2"},
        )
        service.create(create_req)

        # Update with new metadata (merging with existing)
        update_req = AmplifiedDirectoryUpdate(
            metadata={"field1": "updated", "field3": "value3", "default_profile": "foundation/base"}
        )
        result = service.update("preserve", update_req)

        assert result is not None
        # New metadata should merge with existing (not replace)
        assert result.metadata["field1"] == "updated"  # Updated value
        assert result.metadata["field2"] == "value2"  # Preserved from original
        assert result.metadata["field3"] == "value3"  # New field added

    def test_find_parent_amplified_directory(self, service: AmplifiedDirectoryService) -> None:
        """Test _find_parent_amplified_directory helper."""
        # Create grandparent and parent
        service.create(AmplifiedDirectoryCreate(relative_path="grandparent"))
        service.create(AmplifiedDirectoryCreate(relative_path="grandparent/parent"))

        # Find parent for deep child (not yet amplified)
        parent = service._find_parent_amplified_directory("grandparent/parent/child")

        assert parent is not None
        assert parent.name == "parent"

        # Find parent for mid-level child
        parent2 = service._find_parent_amplified_directory("grandparent/not_amplified")

        assert parent2 is not None
        assert parent2.name == "grandparent"

    def test_atomic_metadata_write(self, service: AmplifiedDirectoryService, test_root: Path) -> None:
        """Test that metadata writes are atomic (tmp + rename pattern)."""
        # Create directory
        create_req = AmplifiedDirectoryCreate(relative_path="atomic")
        service.create(create_req)

        metadata_path = test_root / "atomic" / ".amplified" / "metadata.json"
        tmp_path = metadata_path.with_suffix(".tmp")

        # Update metadata
        update_req = AmplifiedDirectoryUpdate(metadata={"test": "atomic", "default_profile": "foundation/base"})
        service.update("atomic", update_req)

        # Verify tmp file doesn't exist after successful write
        assert not tmp_path.exists()
        # Verify metadata file exists and has correct content
        assert metadata_path.exists()

        with open(metadata_path) as f:
            metadata = json.load(f)
        assert metadata["test"] == "atomic"
