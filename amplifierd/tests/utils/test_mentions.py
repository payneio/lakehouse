"""Test mention parsing utilities."""

import pytest

from amplifierd.utils.mentions import extract_mention_path
from amplifierd.utils.mentions import format_mention
from amplifierd.utils.mentions import has_mentions
from amplifierd.utils.mentions import needs_quoting
from amplifierd.utils.mentions import parse_mentions


class TestParseMentions:
    """Test parse_mentions() function."""

    def test_extract_simple_mentions(self) -> None:
        """Extract simple @mentions from text."""
        text = "See @file1.md and @file2.txt"
        mentions = parse_mentions(text)
        assert mentions == ["@file1.md", "@file2.txt"]

    def test_exclude_inline_code_mentions(self) -> None:
        """Exclude @mentions in inline code blocks."""
        text = "Use `@code` not @real"
        mentions = parse_mentions(text)
        assert mentions == ["@real"]

    def test_exclude_double_quoted_strings(self) -> None:
        """Exclude simple @mentions inside regular double quotes (not @"...")."""
        text = 'Skip "@quoted" but include @real'
        mentions = parse_mentions(text)
        # Note: "@quoted" is NOT a valid quoted mention - it's a simple mention inside quotes
        # The @ is inside the quotes, not before them
        assert mentions == ["@real"]

    def test_quoted_mention_with_spaces(self) -> None:
        """Parse @"path with spaces" format."""
        text = 'See @"My Document.md" for details'
        mentions = parse_mentions(text)
        assert mentions == ["@My Document.md"]

    def test_quoted_mention_with_special_chars(self) -> None:
        """Parse @"path with special chars" format."""
        text = 'See @"file (1).md" and @"test [draft].txt"'
        mentions = parse_mentions(text)
        assert mentions == ["@file (1).md", "@test [draft].txt"]

    def test_mixed_simple_and_quoted_mentions(self) -> None:
        """Parse mix of simple and quoted mentions."""
        text = 'See @simple.md and @"path with spaces.md" together'
        mentions = parse_mentions(text)
        assert mentions == ["@path with spaces.md", "@simple.md"]

    def test_quoted_mention_with_nested_path(self) -> None:
        """Parse @"dir/path with spaces/file.md" format."""
        text = 'See @"docs/my folder/README.md"'
        mentions = parse_mentions(text)
        assert mentions == ["@docs/my folder/README.md"]

    def test_exclude_single_quoted_mentions(self) -> None:
        """Exclude @mentions in single quotes."""
        text = "Skip '@quoted' but include @real"
        mentions = parse_mentions(text)
        assert mentions == ["@real"]

    def test_context_key_format(self) -> None:
        """Handle @context-key:path format."""
        text = "See @coding-standards:STYLE.md"
        mentions = parse_mentions(text)
        assert mentions == ["@coding-standards:STYLE.md"]

    def test_path_format(self) -> None:
        """Handle @path format."""
        text = "See @docs/README.md"
        mentions = parse_mentions(text)
        assert mentions == ["@docs/README.md"]

    def test_relative_paths(self) -> None:
        """Handle @./relative and @../relative paths."""
        text = "See @./local.md and @../parent.md"
        mentions = parse_mentions(text)
        assert mentions == ["@./local.md", "@../parent.md"]

    def test_skip_generic_mention_keyword(self) -> None:
        """Skip generic @mention keyword."""
        text = "Use @mention to reference files, like @file.md"
        mentions = parse_mentions(text)
        assert mentions == ["@file.md"]

    def test_preserve_at_prefix(self) -> None:
        """Return mentions with @ prefix intact."""
        text = "See @file.md"
        mentions = parse_mentions(text)
        assert all(m.startswith("@") for m in mentions)

    def test_no_mentions_returns_empty(self) -> None:
        """Return empty list when no mentions found."""
        text = "This text has no mentions"
        mentions = parse_mentions(text)
        assert mentions == []

    def test_multiple_mentions_in_sentence(self) -> None:
        """Extract multiple mentions from single sentence."""
        text = "Compare @file1.md, @file2.md, and @file3.md"
        mentions = parse_mentions(text)
        assert len(mentions) == 3

    def test_mentions_with_underscores_and_dashes(self) -> None:
        """Handle mentions with underscores and dashes."""
        text = "See @my-file_v2.md"
        mentions = parse_mentions(text)
        assert mentions == ["@my-file_v2.md"]

    def test_mentions_not_embedded_in_words(self) -> None:
        """Don't extract @mentions embedded in alphanumeric text."""
        text = "email@example.com is not a mention but @file.md is"
        mentions = parse_mentions(text)
        assert mentions == ["@file.md"]

    def test_mixed_inline_code_and_real_mentions(self) -> None:
        """Handle mix of inline code mentions and real mentions."""
        text = "Reference `@inline.md` and @real.md but not `@another`"
        mentions = parse_mentions(text)
        assert mentions == ["@real.md"]

    def test_multiline_text_with_mentions(self) -> None:
        """Extract mentions from multiline text."""
        text = """
        First line has @file1.md
        Second line has @file2.md
        Third line has @file3.md
        """
        mentions = parse_mentions(text)
        assert len(mentions) == 3


class TestExtractMentionPath:
    """Test extract_mention_path() function."""

    def test_extract_simple_path(self) -> None:
        """Extract path from simple mention."""
        path = extract_mention_path("@file.md")
        assert path == "file.md"

    def test_extract_nested_path(self) -> None:
        """Extract path from nested mention."""
        path = extract_mention_path("@dir/subdir/file.txt")
        assert path == "dir/subdir/file.txt"

    def test_extract_context_key_path(self) -> None:
        """Extract path from context-key mention."""
        path = extract_mention_path("@context-key:path/file.md")
        assert path == "context-key:path/file.md"

    def test_extract_relative_path(self) -> None:
        """Extract relative path."""
        path = extract_mention_path("@./file.md")
        assert path == "./file.md"

    def test_extract_parent_relative_path(self) -> None:
        """Extract parent-relative path."""
        path = extract_mention_path("@../file.md")
        assert path == "../file.md"

    def test_handle_empty_string(self) -> None:
        """Handle empty string input."""
        path = extract_mention_path("@")
        assert path == ""

    def test_handle_no_at_prefix(self) -> None:
        """Handle path without @ prefix."""
        path = extract_mention_path("file.md")
        assert path == "file.md"

    def test_extract_quoted_path(self) -> None:
        """Extract path from quoted mention."""
        path = extract_mention_path('@"My Document.md"')
        assert path == "My Document.md"

    def test_extract_quoted_path_with_spaces(self) -> None:
        """Extract path from quoted mention with spaces."""
        path = extract_mention_path('@"path with spaces/file.md"')
        assert path == "path with spaces/file.md"

    def test_extract_quoted_path_special_chars(self) -> None:
        """Extract path from quoted mention with special characters."""
        path = extract_mention_path('@"file (1) [draft].md"')
        assert path == "file (1) [draft].md"


class TestNeedsQuoting:
    """Test needs_quoting() function."""

    def test_simple_path_no_quoting(self) -> None:
        """Simple paths don't need quoting."""
        assert not needs_quoting("file.md")
        assert not needs_quoting("dir/file.md")
        assert not needs_quoting("my-file_v2.md")

    def test_path_with_space_needs_quoting(self) -> None:
        """Paths with spaces need quoting."""
        assert needs_quoting("My Document.md")
        assert needs_quoting("path with spaces/file.md")

    def test_path_with_special_chars_needs_quoting(self) -> None:
        """Paths with special characters need quoting."""
        assert needs_quoting("file (1).md")
        assert needs_quoting("test [draft].md")
        assert needs_quoting("file#1.md")


class TestFormatMention:
    """Test format_mention() function."""

    def test_format_simple_path(self) -> None:
        """Format simple path without quotes."""
        assert format_mention("file.md") == "@file.md"
        assert format_mention("dir/file.md") == "@dir/file.md"

    def test_format_path_with_spaces(self) -> None:
        """Format path with spaces using quotes."""
        assert format_mention("My Document.md") == '@"My Document.md"'
        assert format_mention("path with spaces/file.md") == '@"path with spaces/file.md"'

    def test_format_path_with_special_chars(self) -> None:
        """Format path with special characters using quotes."""
        assert format_mention("file (1).md") == '@"file (1).md"'


class TestHasMentions:
    """Test has_mentions() function."""

    def test_detects_mention(self) -> None:
        """Detect presence of @mention."""
        assert has_mentions("See @file.md")

    def test_detects_no_mention(self) -> None:
        """Detect absence of @mention."""
        assert not has_mentions("No mentions here")

    def test_detects_multiple_mentions(self) -> None:
        """Detect presence of multiple mentions."""
        assert has_mentions("See @file1.md and @file2.md")

    def test_detects_context_key_mention(self) -> None:
        """Detect context-key format mention."""
        assert has_mentions("See @coding-standards:STYLE.md")

    def test_empty_string_has_no_mentions(self) -> None:
        """Empty string has no mentions."""
        assert not has_mentions("")

    def test_email_not_detected_as_mention(self) -> None:
        """Email addresses not detected as mentions."""
        assert not has_mentions("Contact email@example.com")

    def test_inline_code_mention_still_detected(self) -> None:
        """Note: has_mentions() does not filter inline code.

        This is intentional - it's a quick check for presence.
        parse_mentions() does the filtering.
        """
        assert has_mentions("Use `@code` in examples")

    def test_detects_quoted_mention(self) -> None:
        """Detect presence of quoted @mention."""
        assert has_mentions('See @"My Document.md"')

    def test_detects_quoted_mention_with_spaces(self) -> None:
        """Detect quoted @mention with spaces in path."""
        assert has_mentions('See @"path with spaces/file.md"')
