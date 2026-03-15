"""Tests for MentionResolver service."""

from pathlib import Path

import pytest
from lakehoused.services.mention_resolver import MentionResolver
from lakehoused.services.project_service import PROJECT_MARKER_DIR


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
    project_agents = project_path / PROJECT_MARKER_DIR / "AGENTS.md"
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


class TestAncestorAgentsMdChainResolution:
    """Tests for @mention resolution in ancestor AGENTS.md files.

    These tests verify that @mentions in ancestor AGENTS.md files resolve
    relative to their own directory (the "project root" for that amplified dir),
    NOT relative to the session's project_path.

    Example scenario:
    - Session starts in /data/repos/lakehouse (has .lakehouse/)
    - Ancestor at /data (has .lakehouse/)
    - /data/.lakehouse/AGENTS.md contains @.lakehouse/castle.md
    - Should resolve to /data/.lakehouse/castle.md (NOT /data/repos/lakehouse/.lakehouse/castle.md)
    """

    def test_ancestor_agents_md_mentions_resolve_relative_to_ancestor(self, tmp_path: Path) -> None:
        """@mentions in ancestor AGENTS.md resolve relative to that ancestor's directory."""
        # Setup: Simulate /data/repos/lakehouse scenario
        data_dir = tmp_path / "data"
        project_path = data_dir / "repos" / "lakehouse"
        project_path.mkdir(parents=True)

        # Create project's .lakehouse/AGENTS.md
        project_amplified = project_path / PROJECT_MARKER_DIR
        project_amplified.mkdir()
        (project_amplified / "AGENTS.md").write_text("# Project Instructions\n\nProject-specific guidance.")

        # Create ancestor's .lakehouse/ at /data level
        data_amplified = data_dir / PROJECT_MARKER_DIR
        data_amplified.mkdir()

        # Ancestor AGENTS.md mentions a file relative to /data
        (data_amplified / "AGENTS.md").write_text("# Data-level Instructions\n\nSee @.lakehouse/castle.md for details.")

        # The castle.md file exists at /data/.lakehouse/castle.md
        (data_amplified / "castle.md").write_text("# Castle Configuration\n\nThis is the castle config.")

        # Create resolver with session in project_path
        resolver = MentionResolver(
            compiled_profile_dir=project_path,  # Doesn't matter for this test
            project_path=project_path,
            data_dir=data_dir,
        )

        # Resolve the ancestor chain
        messages = resolver.resolve_agents_md_chain()

        # Should have messages from both AGENTS.md files
        # Plus the resolved @.lakehouse/castle.md from ancestor
        all_content = "\n".join(msg.content for msg in messages)

        # Verify ancestor AGENTS.md content is included
        assert "Data-level Instructions" in all_content

        # Verify project AGENTS.md content is included
        assert "Project Instructions" in all_content

        # KEY TEST: The @.lakehouse/castle.md should have resolved to /data/.lakehouse/castle.md
        assert "Castle Configuration" in all_content, (
            "@.lakehouse/castle.md in ancestor AGENTS.md should resolve relative to /data, "
            "not relative to project_path (/data/repos/lakehouse)"
        )

    def test_nested_mentions_in_ancestor_files_resolve_relative_to_ancestor(self, tmp_path: Path) -> None:
        """Nested @mentions in files loaded from ancestor AGENTS.md also resolve relative to ancestor."""
        # Setup
        data_dir = tmp_path / "data"
        project_path = data_dir / "repos" / "lakehouse"
        project_path.mkdir(parents=True)

        # Create project's .lakehouse/
        (project_path / PROJECT_MARKER_DIR).mkdir()
        (project_path / PROJECT_MARKER_DIR / "AGENTS.md").write_text("# Project")

        # Create ancestor structure at /data
        data_amplified = data_dir / PROJECT_MARKER_DIR
        data_amplified.mkdir()

        # Ancestor AGENTS.md mentions castle.md
        (data_amplified / "AGENTS.md").write_text("See @.lakehouse/castle.md")

        # castle.md in turn mentions another file relative to /data
        (data_amplified / "castle.md").write_text("# Castle\n\nSee @working/whiteboard.md for notes.")

        # Create the working/whiteboard.md at /data level
        working_dir = data_dir / "working"
        working_dir.mkdir()
        (working_dir / "whiteboard.md").write_text("# Whiteboard\n\nActive notes here.")

        resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )

        messages = resolver.resolve_agents_md_chain()
        all_content = "\n".join(msg.content for msg in messages)

        # All three files should be loaded:
        # 1. /data/.lakehouse/AGENTS.md
        # 2. /data/.lakehouse/castle.md (via @.lakehouse/castle.md)
        # 3. /data/working/whiteboard.md (via @working/whiteboard.md in castle.md)
        assert "Castle" in all_content
        assert "Active notes here" in all_content, (
            "Nested @working/whiteboard.md in castle.md should resolve relative to /data"
        )

    def test_mentions_dont_cross_resolve_to_wrong_project(self, tmp_path: Path) -> None:
        """Ensure mentions don't accidentally resolve to session project when ancestor is intended."""
        # This tests the bug scenario directly
        data_dir = tmp_path / "data"
        project_path = data_dir / "repos" / "lakehouse"
        project_path.mkdir(parents=True)

        # Create DIFFERENT castle.md files at both levels
        project_amplified = project_path / PROJECT_MARKER_DIR
        project_amplified.mkdir()
        (project_amplified / "AGENTS.md").write_text("# Project")
        (project_amplified / "castle.md").write_text("WRONG - this is the project castle")

        data_amplified = data_dir / PROJECT_MARKER_DIR
        data_amplified.mkdir()
        (data_amplified / "AGENTS.md").write_text("See @.lakehouse/castle.md")
        (data_amplified / "castle.md").write_text("CORRECT - this is the data castle")

        resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )

        messages = resolver.resolve_agents_md_chain()
        all_content = "\n".join(msg.content for msg in messages)

        # Should get the CORRECT castle from /data/.lakehouse/, not the WRONG one from project
        assert "CORRECT - this is the data castle" in all_content
        # The project's castle.md should NOT be loaded via the ancestor's @mention
        # (it might be loaded if project AGENTS.md mentioned it, but it doesn't)
        assert "WRONG - this is the project castle" not in all_content

    def test_each_ancestor_resolves_relative_to_its_own_directory(self, tmp_path: Path) -> None:
        """Multiple ancestors each resolve their @mentions relative to their own directory."""
        # Setup: /data/projects/myproject with ancestors at /data and /data/projects
        data_dir = tmp_path / "data"
        projects_dir = data_dir / "projects"
        project_path = projects_dir / "myproject"
        project_path.mkdir(parents=True)

        # /data/.lakehouse/AGENTS.md mentions @config/data-config.md
        data_amplified = data_dir / PROJECT_MARKER_DIR
        data_amplified.mkdir()
        (data_amplified / "AGENTS.md").write_text("See @config/data-config.md")
        (data_dir / "config").mkdir()
        (data_dir / "config" / "data-config.md").write_text("DATA LEVEL CONFIG")

        # /data/projects/AGENTS.md mentions @config/projects-config.md
        (projects_dir / "AGENTS.md").write_text("See @config/projects-config.md")
        (projects_dir / "config").mkdir()
        (projects_dir / "config" / "projects-config.md").write_text("PROJECTS LEVEL CONFIG")

        # /data/projects/myproject/.lakehouse/AGENTS.md mentions @config/project-config.md
        (project_path / PROJECT_MARKER_DIR).mkdir()
        (project_path / PROJECT_MARKER_DIR / "AGENTS.md").write_text("See @config/project-config.md")
        (project_path / "config").mkdir()
        (project_path / "config" / "project-config.md").write_text("PROJECT LEVEL CONFIG")

        resolver = MentionResolver(
            compiled_profile_dir=project_path,
            project_path=project_path,
            data_dir=data_dir,
        )

        messages = resolver.resolve_agents_md_chain()
        all_content = "\n".join(msg.content for msg in messages)

        # All three config files should be loaded, each from its correct level
        assert "DATA LEVEL CONFIG" in all_content
        assert "PROJECTS LEVEL CONFIG" in all_content
        assert "PROJECT LEVEL CONFIG" in all_content
