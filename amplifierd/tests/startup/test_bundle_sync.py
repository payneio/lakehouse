"""Tests for bundle registry parsing."""

from pathlib import Path

from amplifierd.startup.bundle_sync import DEFAULT_BUNDLES_TXT
from amplifierd.startup.bundle_sync import ensure_bundles_file
from amplifierd.startup.bundle_sync import parse_bundles_file


class TestEnsureBundlesFile:
    """Tests for BUNDLES.txt creation."""

    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        """Test that BUNDLES.txt is created with defaults when missing."""
        bundles_file = tmp_path / "BUNDLES.txt"
        assert not bundles_file.exists()

        ensure_bundles_file(bundles_file)

        assert bundles_file.exists()
        content = bundles_file.read_text()
        assert "amplifier-dev" in content
        assert "minimal" in content
        assert "software-developer" in content

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        """Test that existing BUNDLES.txt is not overwritten."""
        bundles_file = tmp_path / "BUNDLES.txt"
        custom_content = "# My custom bundles\nmy-bundle:git+https://github.com/me/repo#bundle.md"
        bundles_file.write_text(custom_content)

        ensure_bundles_file(bundles_file)

        assert bundles_file.read_text() == custom_content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created."""
        bundles_file = tmp_path / "nested" / "dir" / "BUNDLES.txt"
        assert not bundles_file.parent.exists()

        ensure_bundles_file(bundles_file)

        assert bundles_file.exists()


class TestParseBundlesFile:
    """Tests for BUNDLES.txt parsing."""

    def test_parses_valid_entries(self, tmp_path: Path) -> None:
        """Test parsing valid bundle entries."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text(
            """
# Comment line
amplifier-dev:git+https://github.com/microsoft/amplifier-foundation@main#bundles/amplifier-dev.md
minimal:git+https://github.com/microsoft/amplifier-foundation@main#bundles/minimal.md
"""
        )

        bundles = parse_bundles_file(bundles_file)

        assert len(bundles) == 2
        assert bundles["amplifier-dev"] == "git+https://github.com/microsoft/amplifier-foundation@main#bundles/amplifier-dev.md"
        assert bundles["minimal"] == "git+https://github.com/microsoft/amplifier-foundation@main#bundles/minimal.md"

    def test_skips_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text(
            """
name1:ref1

name2:ref2
"""
        )

        bundles = parse_bundles_file(bundles_file)

        assert len(bundles) == 2

    def test_skips_comments(self, tmp_path: Path) -> None:
        """Test that comment lines are skipped."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text(
            """# Comment 1
name1:ref1
# Comment 2
name2:ref2
"""
        )

        bundles = parse_bundles_file(bundles_file)

        assert len(bundles) == 2

    def test_skips_invalid_lines(self, tmp_path: Path) -> None:
        """Test that invalid lines (no colon) are skipped."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text(
            """name1:ref1
invalid_line_without_colon
name2:ref2
"""
        )

        bundles = parse_bundles_file(bundles_file)

        assert len(bundles) == 2

    def test_parses_default_content(self, tmp_path: Path) -> None:
        """Test that default BUNDLES.txt content parses correctly."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text(DEFAULT_BUNDLES_TXT)

        bundles = parse_bundles_file(bundles_file)

        # Should have 4 entries from the default content
        assert len(bundles) == 4
        assert "amplifier-dev" in bundles
        assert "minimal" in bundles
        assert "software-developer" in bundles
        assert "basic" in bundles

    def test_returns_dict_not_list(self, tmp_path: Path) -> None:
        """Test that parse_bundles_file returns dict[str, str]."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text("test-bundle:git+https://github.com/test/repo@main#bundle.md")

        bundles = parse_bundles_file(bundles_file)

        assert isinstance(bundles, dict)
        assert bundles["test-bundle"] == "git+https://github.com/test/repo@main#bundle.md"

    def test_handles_colons_in_uri(self, tmp_path: Path) -> None:
        """Test that URIs with colons (e.g., https://) are parsed correctly."""
        bundles_file = tmp_path / "BUNDLES.txt"
        bundles_file.write_text("my-bundle:git+https://github.com/user/repo@main#path/to/bundle.md")

        bundles = parse_bundles_file(bundles_file)

        assert bundles["my-bundle"] == "git+https://github.com/user/repo@main#path/to/bundle.md"
