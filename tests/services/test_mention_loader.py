"""Test MentionLoader service."""

from pathlib import Path

import pytest

from amplifierd.services.mention_loader import MentionLoader


class TestMentionLoader:
    """Test MentionLoader service."""

    @pytest.fixture
    def test_profile_dir(self, tmp_path: Path) -> Path:
        """Create test profile with contexts."""
        profile_dir = tmp_path / "share" / "profiles" / "test-collection" / "test-profile"
        profile_dir.mkdir(parents=True)

        # Create contexts directory
        contexts_dir = profile_dir / "contexts"
        contexts_dir.mkdir()

        # Create coding-standards context
        coding_standards = contexts_dir / "coding-standards"
        coding_standards.mkdir()
        (coding_standards / "STYLE.md").write_text("# Style Guide\n\nUse tabs for indentation.")
        (coding_standards / "PATTERNS.md").write_text(
            "# Patterns\n\nSee also: @coding-standards:STYLE.md\n\nUse factory pattern."
        )

        # Create best-practices context
        best_practices = contexts_dir / "best-practices"
        best_practices.mkdir()
        (best_practices / "TESTING.md").write_text("# Testing Best Practices\n\nWrite tests first.")

        return profile_dir

    @pytest.fixture
    def test_amplified_dir(self, tmp_path: Path) -> Path:
        """Create test amplified directory."""
        amp_dir = tmp_path / "project"
        amp_dir.mkdir()

        # Create test files
        docs_dir = amp_dir / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Project Docs\n\nWelcome to the project.")
        (docs_dir / "STYLE.md").write_text(
            "# Local Style\n\nSee standard: @coding-standards:PATTERNS.md\n\nPrefer arrow functions."
        )

        # Create nested structure
        guides_dir = docs_dir / "guides"
        guides_dir.mkdir()
        (guides_dir / "getting-started.md").write_text("# Getting Started\n\nSee @docs/README.md")

        return amp_dir

    @pytest.fixture
    def loader(self, test_profile_dir: Path, test_amplified_dir: Path) -> MentionLoader:
        """Create MentionLoader with test directories."""
        return MentionLoader(compiled_profile_dir=test_profile_dir, amplified_dir=test_amplified_dir)

    def test_resolve_context_key_format(self, loader: MentionLoader) -> None:
        """Resolve @context-key:path to compiled profile contexts/."""
        text = "See @coding-standards:STYLE.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 1
        assert "Use tabs for indentation" in messages[0].content
        assert "@coding-standards:STYLE.md" in messages[0].content

    def test_resolve_path_to_amplified_dir(self, loader: MentionLoader) -> None:
        """Resolve @path to amplified_dir."""
        text = "See @docs/README.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 1
        assert "Welcome to the project" in messages[0].content

    def test_recursive_resolution(self, loader: MentionLoader) -> None:
        """Recursive resolution - follow nested @mentions."""
        # PATTERNS.md mentions STYLE.md
        text = "See @coding-standards:PATTERNS.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        # Should load both PATTERNS.md and STYLE.md
        assert len(messages) == 2

        contents = [msg.content for msg in messages]
        assert any("Use factory pattern" in c for c in contents)
        assert any("Use tabs for indentation" in c for c in contents)

    def test_cycle_detection(self, tmp_path: Path) -> None:
        """Cycle detection - don't loop infinitely."""
        # Create files with circular references
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "test"
        contexts.mkdir(parents=True)

        (contexts / "A.md").write_text("# File A\nSee @test:B.md")
        (contexts / "B.md").write_text("# File B\nSee @test:A.md")

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @test:A.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        # Should load both A and B exactly once
        assert len(messages) == 2

    def test_content_deduplication_across_mentions(self, tmp_path: Path) -> None:
        """Content deduplication across multiple @mentions."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "shared"
        contexts.mkdir(parents=True)

        # Same content in different files
        content = "# Shared Content\n\nThis is duplicated."
        (contexts / "file1.md").write_text(content)
        (contexts / "file2.md").write_text(content)

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @shared:file1.md and @shared:file2.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        # Should deduplicate - only one message
        assert len(messages) == 1

        # But should credit both @mentions
        assert "@shared:file1.md" in messages[0].content
        assert "@shared:file2.md" in messages[0].content

    def test_graceful_skip_on_missing_file(self, loader: MentionLoader, caplog: pytest.LogCaptureFixture) -> None:
        """Gracefully skip when file doesn't exist."""
        text = "See @nonexistent:MISSING.md and @coding-standards:STYLE.md"

        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        # Should load the existing file
        assert len(messages) == 1
        assert "Use tabs" in messages[0].content

        # Should log warning about missing file
        assert "not found" in caplog.text.lower()

    def test_security_block_path_traversal(self, loader: MentionLoader, caplog: pytest.LogCaptureFixture) -> None:
        """Block path traversal attempts."""
        # Attempt to escape amplified_dir
        text = "See @../../../etc/passwd"

        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 0, "Should block path traversal"
        assert "path traversal" in caplog.text.lower() or "escapes" in caplog.text.lower()

    def test_message_creation_format(self, loader: MentionLoader) -> None:
        """Message creation has correct format."""
        text = "See @coding-standards:STYLE.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 1
        msg = messages[0]

        # Verify message structure
        assert msg.role == "developer"
        assert "[Context from" in msg.content
        assert "@coding-standards:STYLE.md" in msg.content
        assert "→" in msg.content  # Shows resolution path
        assert "\n\n" in msg.content  # Separates header from content
        assert "# Style Guide" in msg.content

    def test_multiple_paths_to_same_content(self, tmp_path: Path) -> None:
        """Multiple paths to same content are all credited."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "test"
        contexts.mkdir(parents=True)

        content = "# Shared\n\nSame content"
        (contexts / "v1.md").write_text(content)
        (contexts / "v2.md").write_text(content)
        (contexts / "v3.md").write_text(content)

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @test:v1.md and @test:v2.md and @test:v3.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        assert len(messages) == 1

        # All paths should be credited
        msg_content = messages[0].content
        assert "@test:v1.md" in msg_content
        assert "@test:v2.md" in msg_content
        assert "@test:v3.md" in msg_content

    def test_source_mentions_tracked(self, loader: MentionLoader) -> None:
        """Source mentions are tracked in message metadata."""
        text = "See @coding-standards:STYLE.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 1
        assert hasattr(messages[0], "source_mentions")
        assert "@coding-standards:STYLE.md" in messages[0].source_mentions

    def test_missing_context_directory(self, loader: MentionLoader, caplog: pytest.LogCaptureFixture) -> None:
        """Handle missing context directory gracefully."""
        text = "See @nonexistent-context:file.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 0
        assert "not found" in caplog.text.lower()

    def test_empty_text_returns_no_messages(self, loader: MentionLoader) -> None:
        """Empty text returns no messages."""
        messages = loader.load_mentions("", relative_to=loader.amplified_dir)
        assert len(messages) == 0

    def test_text_with_no_mentions_returns_empty(self, loader: MentionLoader) -> None:
        """Text without mentions returns empty list."""
        text = "This text has no mentions at all"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)
        assert len(messages) == 0

    def test_invalid_context_mention_format(self, loader: MentionLoader, caplog: pytest.LogCaptureFixture) -> None:
        """Handle invalid context mention format."""
        text = "See @context:with:too:many:colons"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 0
        assert "invalid" in caplog.text.lower()

    def test_nested_mentions_in_multiple_files(self, loader: MentionLoader) -> None:
        """Follow nested mentions through multiple levels."""
        # docs/STYLE.md mentions coding-standards:PATTERNS.md
        # coding-standards:PATTERNS.md mentions coding-standards:STYLE.md
        text = "See @docs/STYLE.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        # Should load: docs/STYLE.md, PATTERNS.md, and STYLE.md (from context)
        assert len(messages) == 3

        contents = [msg.content for msg in messages]
        assert any("Local Style" in c for c in contents)
        assert any("Use factory pattern" in c for c in contents)
        assert any("Use tabs" in c for c in contents)

    def test_file_read_errors_handled_gracefully(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Handle file read errors gracefully."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "test"
        contexts.mkdir(parents=True)

        # Create directory instead of file (will cause read error)
        bad_file = contexts / "bad.md"
        bad_file.mkdir()

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @test:bad.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        assert len(messages) == 0
        assert "failed" in caplog.text.lower() or "error" in caplog.text.lower()

    def test_unicode_in_file_content(self, tmp_path: Path) -> None:
        """Handle Unicode in file content (not paths - pattern is ASCII-only)."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "test"
        contexts.mkdir(parents=True)

        # Note: Mention pattern only matches ASCII filenames
        # But content can contain Unicode
        (contexts / "unicode.md").write_text("# Unicode content 测试 🎉")

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @test:unicode.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        assert len(messages) == 1
        assert "Unicode content" in messages[0].content
        assert "测试" in messages[0].content
        assert "🎉" in messages[0].content

    def test_relative_to_parameter_used_correctly(self, loader: MentionLoader) -> None:
        """relative_to parameter is used for context (though not affecting resolution in current impl)."""
        # This test verifies the parameter exists and doesn't cause errors
        # The actual relative path resolution happens via amplified_dir
        text = "See @docs/README.md"
        different_relative = loader.amplified_dir / "docs"

        messages = loader.load_mentions(text, relative_to=different_relative)

        assert len(messages) == 1
        assert "Welcome to the project" in messages[0].content

    def test_both_mention_types_in_same_file(self, loader: MentionLoader) -> None:
        """Can use both @context-key:path and @path in same text."""
        text = "See @coding-standards:STYLE.md and @docs/README.md"
        messages = loader.load_mentions(text, relative_to=loader.amplified_dir)

        assert len(messages) == 2

        contents = [msg.content for msg in messages]
        assert any("Use tabs" in c for c in contents)
        assert any("Welcome to the project" in c for c in contents)

    def test_large_file_handling(self, tmp_path: Path) -> None:
        """Handle large files efficiently."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        contexts = profile_dir / "contexts" / "test"
        contexts.mkdir(parents=True)

        # Create large file
        large_content = "# Large File\n\n" + ("Content line\n" * 10000)
        (contexts / "large.md").write_text(large_content)

        amp_dir = tmp_path / "amp"
        amp_dir.mkdir()

        loader = MentionLoader(compiled_profile_dir=profile_dir, amplified_dir=amp_dir)

        text = "See @test:large.md"
        messages = loader.load_mentions(text, relative_to=amp_dir)

        assert len(messages) == 1
        assert len(messages[0].content) > 100000
