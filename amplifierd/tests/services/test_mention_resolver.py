"""Tests for MentionResolver service."""

import pytest
from pathlib import Path
from amplifierd.services.mention_resolver import MentionResolver
from amplifierd.models.context_messages import ContextMessage


@pytest.fixture
def test_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create test directories with sample files."""
    compiled_profile = tmp_path / "compiled_profile"
    amplified_dir = tmp_path / "project"

    compiled_profile.mkdir(parents=True)
    amplified_dir.mkdir(parents=True)

    # Create AGENTS.md with mentions
    agents_md = amplified_dir / "AGENTS.md"
    agents_md.write_text("See @README.md for details.")

    # Create README.md
    readme = amplified_dir / "README.md"
    readme.write_text("# Project README\n\nThis is the project.")

    # Create context directory structure
    contexts_dir = compiled_profile / "contexts"
    contexts_dir.mkdir()

    test_context = contexts_dir / "test-context"
    test_context.mkdir()

    context_file = test_context / "context.md"
    context_file.write_text("# Context File\n\nContext information.")

    return compiled_profile, amplified_dir


def test_resolver_initialization(test_dirs: tuple[Path, Path]) -> None:
    """Test resolver initializes correctly."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    assert resolver.compiled_profile_dir == compiled_profile.resolve()
    assert resolver.amplified_dir == amplified_dir.resolve()
    assert resolver.loader is not None


def test_resolve_profile_instructions_with_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving mentions from profile instructions."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    instructions = "Follow @test-context:context.md for guidance."
    messages = resolver.resolve_profile_instructions(instructions)

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Context File" in messages[0].content
    assert "@test-context:context.md" in messages[0].source_mentions[0]


def test_resolve_profile_instructions_no_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving instructions with no mentions."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    instructions = "Just plain instructions without mentions."
    messages = resolver.resolve_profile_instructions(instructions)

    assert messages == []


def test_resolve_agents_md(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving mentions from AGENTS.md."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    messages = resolver.resolve_agents_md()

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Project README" in messages[0].content


def test_resolve_agents_md_missing_file(tmp_path: Path) -> None:
    """Test handling missing AGENTS.md gracefully."""
    compiled_profile = tmp_path / "compiled_profile"
    amplified_dir = tmp_path / "project"

    compiled_profile.mkdir()
    amplified_dir.mkdir()

    resolver = MentionResolver(compiled_profile, amplified_dir)
    messages = resolver.resolve_agents_md()

    assert messages == []


def test_resolve_runtime_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving runtime mentions from user message."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    user_message = "Check @README.md please."
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should include AGENTS.md mentions + user message mentions
    # AGENTS.md references @README.md, user also references @README.md
    # Since they're loaded separately, we get 2 messages (no cross-load deduplication)
    assert len(messages) == 2
    assert all("Project README" in msg.content for msg in messages)


def test_resolve_runtime_mentions_no_user_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test runtime resolution with no user mentions."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    user_message = "Just a regular message."
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should only get AGENTS.md mentions
    assert len(messages) == 1
    assert "Project README" in messages[0].content


def test_resolve_runtime_mentions_order(test_dirs: tuple[Path, Path]) -> None:
    """Test that AGENTS.md mentions come before user mentions."""
    compiled_profile, amplified_dir = test_dirs
    resolver = MentionResolver(compiled_profile, amplified_dir)

    # Create a second file
    other = amplified_dir / "OTHER.md"
    other.write_text("Other content")

    user_message = "See @OTHER.md"
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should have README.md (from AGENTS.md) first, then OTHER.md (from user)
    assert len(messages) == 2
    assert "Project README" in messages[0].content
    assert "Other content" in messages[1].content
