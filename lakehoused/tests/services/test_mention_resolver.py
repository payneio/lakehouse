"""Tests for MentionResolver service."""

import pytest
from pathlib import Path
from lakehoused.services.mention_resolver import MentionResolver
from lakehoused.models.context_messages import ContextMessage


@pytest.fixture
def test_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create test directories with sample files."""
    compiled_profile = tmp_path / "compiled_profile"
    project_path = tmp_path / "project"

    compiled_profile.mkdir(parents=True)
    project_path.mkdir(parents=True)

    # Create AGENTS.md with mentions
    agents_md = project_path / "AGENTS.md"
    agents_md.write_text("See @README.md for details.")

    # Create README.md
    readme = project_path / "README.md"
    readme.write_text("# Project README\n\nThis is the project.")

    # Create context directory structure
    contexts_dir = compiled_profile / "contexts"
    contexts_dir.mkdir()

    test_context = contexts_dir / "test-context"
    test_context.mkdir()

    context_file = test_context / "context.md"
    context_file.write_text("# Context File\n\nContext information.")

    return compiled_profile, project_path


def test_resolver_initialization(test_dirs: tuple[Path, Path]) -> None:
    """Test resolver initializes correctly."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    assert resolver.compiled_profile_dir == compiled_profile.resolve()
    assert resolver.project_path == project_path.resolve()
    assert resolver.loader is not None


def test_resolve_profile_instructions_with_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving mentions from profile instructions."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    instructions = "Follow @test-context:context.md for guidance."
    messages = resolver.resolve_profile_instructions(instructions)

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Context File" in messages[0].content
    assert "@test-context:context.md" in messages[0].source_mentions[0]


def test_resolve_profile_instructions_no_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving instructions with no mentions."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    instructions = "Just plain instructions without mentions."
    messages = resolver.resolve_profile_instructions(instructions)

    assert messages == []


def test_resolve_agents_md(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving mentions from AGENTS.md."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    messages = resolver.resolve_agents_md()

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Project README" in messages[0].content


def test_resolve_agents_md_missing_file(tmp_path: Path) -> None:
    """Test handling missing AGENTS.md gracefully."""
    compiled_profile = tmp_path / "compiled_profile"
    project_path = tmp_path / "project"

    compiled_profile.mkdir()
    project_path.mkdir()

    resolver = MentionResolver(compiled_profile, project_path)
    messages = resolver.resolve_agents_md()

    assert messages == []


def test_resolve_runtime_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving runtime mentions from user message.

    NOTE: resolve_runtime_mentions only resolves user @mentions.
    The ancestor AGENTS.md chain is resolved separately during session creation.
    """
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    user_message = "Check @README.md please."
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should only include user @mentions (ancestor chain is handled separately)
    assert len(messages) == 1
    assert "Project README" in messages[0].content


def test_resolve_runtime_mentions_no_user_mentions(test_dirs: tuple[Path, Path]) -> None:
    """Test runtime resolution with no user mentions.

    NOTE: resolve_runtime_mentions only resolves user @mentions.
    With no @mentions in the message, it returns empty list.
    """
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    user_message = "Just a regular message."
    messages = resolver.resolve_runtime_mentions(user_message)

    # No @mentions in user message = empty result
    assert messages == []


def test_resolve_runtime_mentions_order(test_dirs: tuple[Path, Path]) -> None:
    """Test resolving multiple user mentions."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    # Create a second file
    other = project_path / "OTHER.md"
    other.write_text("Other content")

    user_message = "See @OTHER.md"
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should only have user @mentions (ancestor chain is handled separately)
    assert len(messages) == 1
    assert "Other content" in messages[0].content


def test_resolve_agents_md_chain_deduplication(tmp_path: Path) -> None:
    """Test that resolve_agents_md_chain excludes paths already loaded via @mentions."""
    # Create directory hierarchy
    data_dir = tmp_path / "data"
    project_path = data_dir / "projects" / "my-project"
    project_path.mkdir(parents=True)

    # Create project AGENTS.md
    project_agents = project_path / ".amplified" / "AGENTS.md"
    project_agents.parent.mkdir(parents=True)
    project_agents.write_text("Project-specific instructions")

    # Create parent AGENTS.md
    parent_agents = data_dir / "projects" / "AGENTS.md"
    parent_agents.write_text("Parent project instructions")

    resolver = MentionResolver(
        compiled_profile_dir=project_path,
        project_path=project_path,
        data_dir=data_dir,
    )

    # First, resolve without exclusion - should get both
    messages_full = resolver.resolve_agents_md_chain()
    assert len(messages_full) == 2  # Parent + project AGENTS.md

    # Now, pretend the project AGENTS.md was already loaded via @mention
    exclude = {project_agents.resolve()}
    messages_dedup = resolver.resolve_agents_md_chain(exclude_paths=exclude)

    # Should only get parent, not project (since it's excluded)
    assert len(messages_dedup) == 1
    assert "Parent project instructions" in messages_dedup[0].content
    assert "Project-specific instructions" not in messages_dedup[0].content


def test_resolve_profile_instructions_with_paths(test_dirs: tuple[Path, Path]) -> None:
    """Test that resolve_profile_instructions_with_paths returns resolved paths."""
    compiled_profile, project_path = test_dirs
    resolver = MentionResolver(compiled_profile, project_path)

    instructions = "Follow @test-context:context.md for guidance."
    messages, resolved_paths = resolver.resolve_profile_instructions_with_paths(instructions)

    assert len(messages) == 1
    assert len(resolved_paths) == 1
    # The resolved path should exist and be the context file
    resolved_path = list(resolved_paths)[0]
    assert resolved_path.exists()
    assert resolved_path.name == "context.md"
