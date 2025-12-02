"""Test ContentDeduplicator service."""

from pathlib import Path

import pytest

from amplifierd.services.content_deduplicator import ContentDeduplicator


class TestContentDeduplicator:
    """Test ContentDeduplicator class."""

    @pytest.fixture
    def deduplicator(self) -> ContentDeduplicator:
        """Create fresh deduplicator for each test."""
        return ContentDeduplicator()

    def test_add_single_file(self, deduplicator: ContentDeduplicator) -> None:
        """Add single file."""
        path = Path("/test/file.md")
        content = "# Test Content"

        deduplicator.add_file(path, content)
        files = deduplicator.get_unique_files()

        assert len(files) == 1
        assert files[0].content == content
        assert files[0].paths == [path]

    def test_add_multiple_files_same_content(self, deduplicator: ContentDeduplicator) -> None:
        """Add multiple files with same content - should deduplicate."""
        path1 = Path("/test/file1.md")
        path2 = Path("/test/file2.md")
        content = "# Shared Content"

        deduplicator.add_file(path1, content)
        deduplicator.add_file(path2, content)

        files = deduplicator.get_unique_files()

        assert len(files) == 1, "Should deduplicate identical content"
        assert files[0].content == content
        assert set(files[0].paths) == {path1, path2}

    def test_add_files_different_content(self, deduplicator: ContentDeduplicator) -> None:
        """Add files with different content - should keep separate."""
        path1 = Path("/test/file1.md")
        path2 = Path("/test/file2.md")
        content1 = "# Content 1"
        content2 = "# Content 2"

        deduplicator.add_file(path1, content1)
        deduplicator.add_file(path2, content2)

        files = deduplicator.get_unique_files()

        assert len(files) == 2, "Should keep different content separate"
        contents = {f.content for f in files}
        assert contents == {content1, content2}

    def test_track_all_paths_for_deduplicated_content(self, deduplicator: ContentDeduplicator) -> None:
        """Track all paths when content is deduplicated."""
        paths = [
            Path("/test/v1/file.md"),
            Path("/test/v2/file.md"),
            Path("/test/v3/file.md"),
        ]
        content = "# Same content everywhere"

        for path in paths:
            deduplicator.add_file(path, content)

        files = deduplicator.get_unique_files()

        assert len(files) == 1
        assert set(files[0].paths) == set(paths)

    def test_get_unique_files_returns_context_files(self, deduplicator: ContentDeduplicator) -> None:
        """get_unique_files() returns correct ContextFile objects."""
        path = Path("/test/file.md")
        content = "# Test"

        deduplicator.add_file(path, content)
        files = deduplicator.get_unique_files()

        assert len(files) == 1
        ctx_file = files[0]

        # Verify ContextFile structure
        assert hasattr(ctx_file, "content")
        assert hasattr(ctx_file, "paths")
        assert hasattr(ctx_file, "hash")

        assert ctx_file.content == content
        assert ctx_file.paths == [path]
        assert isinstance(ctx_file.hash, str)
        assert len(ctx_file.hash) == 64  # SHA-256 hex digest length

    def test_content_hashing_is_consistent(self, deduplicator: ContentDeduplicator) -> None:
        """Content hashing produces consistent results."""
        path1 = Path("/test/file1.md")
        path2 = Path("/test/file2.md")
        content = "# Test Content\n\nSame everywhere"

        deduplicator.add_file(path1, content)
        hash1 = deduplicator.get_known_hashes().pop()

        deduplicator2 = ContentDeduplicator()
        deduplicator2.add_file(path2, content)
        hash2 = deduplicator2.get_known_hashes().pop()

        assert hash1 == hash2, "Same content should produce same hash"

    def test_get_known_hashes(self, deduplicator: ContentDeduplicator) -> None:
        """get_known_hashes() returns tracked hashes."""
        path1 = Path("/test/file1.md")
        path2 = Path("/test/file2.md")
        content1 = "Content 1"
        content2 = "Content 2"

        deduplicator.add_file(path1, content1)
        deduplicator.add_file(path2, content2)

        hashes = deduplicator.get_known_hashes()

        assert len(hashes) == 2
        assert all(isinstance(h, str) for h in hashes)
        assert all(len(h) == 64 for h in hashes)

    def test_add_same_path_twice_same_content(self, deduplicator: ContentDeduplicator) -> None:
        """Adding same path twice with same content doesn't duplicate."""
        path = Path("/test/file.md")
        content = "# Content"

        deduplicator.add_file(path, content)
        deduplicator.add_file(path, content)

        files = deduplicator.get_unique_files()

        assert len(files) == 1
        assert files[0].paths == [path], "Path should only appear once"

    def test_empty_content_handling(self, deduplicator: ContentDeduplicator) -> None:
        """Handle empty content correctly."""
        path1 = Path("/test/empty1.md")
        path2 = Path("/test/empty2.md")
        content = ""

        deduplicator.add_file(path1, content)
        deduplicator.add_file(path2, content)

        files = deduplicator.get_unique_files()

        assert len(files) == 1, "Empty content should also deduplicate"
        assert set(files[0].paths) == {path1, path2}

    def test_whitespace_differences_not_deduplicated(self, deduplicator: ContentDeduplicator) -> None:
        """Whitespace differences result in different content."""
        path1 = Path("/test/file1.md")
        path2 = Path("/test/file2.md")
        content1 = "Content"
        content2 = "Content "  # Trailing space

        deduplicator.add_file(path1, content1)
        deduplicator.add_file(path2, content2)

        files = deduplicator.get_unique_files()

        assert len(files) == 2, "Whitespace differences should not deduplicate"

    def test_large_content_handling(self, deduplicator: ContentDeduplicator) -> None:
        """Handle large content efficiently."""
        path = Path("/test/large.md")
        content = "# Large Content\n" * 10000  # ~160KB

        deduplicator.add_file(path, content)
        files = deduplicator.get_unique_files()

        assert len(files) == 1
        assert len(files[0].content) > 100000

    def test_unicode_content_handling(self, deduplicator: ContentDeduplicator) -> None:
        """Handle Unicode content correctly."""
        path1 = Path("/test/unicode1.md")
        path2 = Path("/test/unicode2.md")
        content = "# Testing 测试 テスト 🎉"

        deduplicator.add_file(path1, content)
        deduplicator.add_file(path2, content)

        files = deduplicator.get_unique_files()

        assert len(files) == 1, "Unicode content should deduplicate"
        assert files[0].content == content
