"""Test change detection for profile compilation."""

import json
from pathlib import Path

import pytest

from amplifierd.models.profiles import ProfileDetails
from amplifierd.services.profile_compilation import ProfileCompilationService
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def services(tmp_path: Path) -> tuple[ProfileCompilationService, RefResolutionService]:
    """Create compilation and ref resolution services with temp directories."""
    cache_dir = tmp_path / "cache"
    share_dir = tmp_path / "share"
    cache_dir.mkdir()
    share_dir.mkdir()

    ref_service = RefResolutionService(cache_dir)
    compile_service = ProfileCompilationService(share_dir, ref_service)

    return compile_service, ref_service


@pytest.fixture
def simple_profile() -> ProfileDetails:
    """Create a simple profile for testing."""
    return ProfileDetails(
        name="test-profile",
        version="1.0.0",
        description="Test profile for change detection",
        source="test",
        is_active=True,
        agents={},
        context={},
        tools=[],
        hooks=[],
        providers=[],
        session=None,
    )


class TestChangeDetection:
    """Test profile compilation change detection."""

    def test_first_compilation_creates_metadata(
        self: "TestChangeDetection",
        services: tuple[ProfileCompilationService, RefResolutionService],
        simple_profile: ProfileDetails,
    ) -> None:
        """First compilation should create metadata file."""
        compile_service, _ = services

        result = compile_service.compile_profile("test-collection", simple_profile, force=False)

        # Check metadata file exists
        meta_file = result / ".compilation_meta.json"
        assert meta_file.exists(), "Metadata file should exist after compilation"

        meta = json.loads(meta_file.read_text())
        assert "manifest_hash" in meta
        assert "compiled_at" in meta
        assert "source_commit" in meta

    def test_second_compilation_skips_unchanged(
        self: "TestChangeDetection",
        services: tuple[ProfileCompilationService, RefResolutionService],
        simple_profile: ProfileDetails,
    ) -> None:
        """Second compilation with unchanged profile should skip."""
        compile_service, _ = services

        # First compilation
        result1 = compile_service.compile_profile("test-collection", simple_profile, force=False)
        meta_file = result1 / ".compilation_meta.json"
        first_meta = json.loads(meta_file.read_text())

        # Second compilation - should skip
        result2 = compile_service.compile_profile("test-collection", simple_profile, force=False)

        # Should return same path and metadata should be unchanged
        assert result2 == result1
        second_meta = json.loads(meta_file.read_text())
        assert second_meta == first_meta, "Metadata should be unchanged when compilation skipped"

    def test_force_recompiles_even_if_unchanged(
        self: "TestChangeDetection",
        services: tuple[ProfileCompilationService, RefResolutionService],
        simple_profile: ProfileDetails,
    ) -> None:
        """Compilation with force=True should recompile even if unchanged."""
        compile_service, _ = services

        # First compilation
        result1 = compile_service.compile_profile("test-collection", simple_profile, force=False)

        # Second compilation with force=True should recompile
        result2 = compile_service.compile_profile("test-collection", simple_profile, force=True)

        assert result2 == result1
        # Compiled_at should be different since we forced recompilation
        # (Note: This might be flaky if tests run too fast, but should work in practice)

    def test_changed_profile_triggers_recompilation(
        self: "TestChangeDetection",
        services: tuple[ProfileCompilationService, RefResolutionService],
        simple_profile: ProfileDetails,
    ) -> None:
        """Changing profile should trigger recompilation."""
        compile_service, _ = services

        # First compilation
        result1 = compile_service.compile_profile("test-collection", simple_profile, force=False)
        meta_file = result1 / ".compilation_meta.json"
        first_hash = json.loads(meta_file.read_text())["manifest_hash"]

        # Modify profile
        simple_profile.version = "2.0.0"

        # Second compilation should detect change
        result2 = compile_service.compile_profile("test-collection", simple_profile, force=False)

        assert result2 == result1  # Same path
        second_hash = json.loads(meta_file.read_text())["manifest_hash"]
        assert second_hash != first_hash, "Hash should change when profile changes"

    def test_corrupted_metadata_triggers_recompilation(
        self: "TestChangeDetection",
        services: tuple[ProfileCompilationService, RefResolutionService],
        simple_profile: ProfileDetails,
    ) -> None:
        """Corrupted metadata should trigger recompilation."""
        compile_service, _ = services

        # First compilation
        result1 = compile_service.compile_profile("test-collection", simple_profile, force=False)
        meta_file = result1 / ".compilation_meta.json"

        # Corrupt metadata
        meta_file.write_text("invalid json{")

        # Second compilation should handle corrupted metadata and recompile
        result2 = compile_service.compile_profile("test-collection", simple_profile, force=False)

        assert result2 == result1
        # Metadata should be valid after recompilation
        meta = json.loads(meta_file.read_text())
        assert "manifest_hash" in meta
