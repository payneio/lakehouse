"""Service for resolving @mentions from various sources into context messages.

This service provides a unified interface for resolving @mentions from:
- Profile instructions
- AGENTS.md files
- Runtime user messages

It delegates to MentionLoader for actual resolution while handling file I/O
and error handling at a higher level.
"""

import logging
from pathlib import Path

from lakehoused.models.context_messages import ContextMessage
from lakehoused.services.mention_loader import MentionLoader
from lakehoused.utils.mentions import has_mentions

logger = logging.getLogger(__name__)


class MentionResolver:
    """Resolves @mentions from various sources into context messages."""

    def __init__(
        self: "MentionResolver",
        compiled_profile_dir: Path,
        project_path: Path,
        data_dir: Path | None = None,
        loader: MentionLoader | None = None,
        source_base_paths: dict[str, Path] | None = None,
    ) -> None:
        """Initialize resolver with context directories.

        Args:
            compiled_profile_dir: Path to compiled profile directory
            project_path: Path to project directory (project root)
            data_dir: Path to data directory (for security validation). Defaults to project_path.parent if not provided.
            loader: Optional MentionLoader instance (creates default if None)
            source_base_paths: Dict mapping bundle namespace to base_path for @namespace:path resolution.
                Enables @foundation:context/file.md to resolve to Foundation bundle's context directory.
        """
        self.compiled_profile_dir = compiled_profile_dir.resolve()
        self.project_path = project_path.resolve()
        self.data_dir = data_dir.resolve() if data_dir is not None else project_path.parent.resolve()
        self.source_base_paths = source_base_paths or {}
        self.loader = loader or MentionLoader(
            compiled_profile_dir=self.compiled_profile_dir,
            project_path=self.project_path,
            data_dir=self.data_dir,
            source_base_paths=self.source_base_paths,
        )

    def resolve_profile_instructions(
        self: "MentionResolver",
        instructions: str,
    ) -> list[ContextMessage]:
        """Resolve mentions from profile instructions field.

        Args:
            instructions: Profile instructions with potential @mentions

        Returns:
            List of context messages from resolved mentions
        """
        messages, _ = self.resolve_profile_instructions_with_paths(instructions)
        return messages

    def resolve_profile_instructions_with_paths(
        self: "MentionResolver",
        instructions: str,
    ) -> tuple[list[ContextMessage], set[Path]]:
        """Resolve mentions from profile instructions and return resolved paths.

        Same as resolve_profile_instructions() but also returns the set of
        resolved paths, useful for deduplication with ancestor AGENTS.md chain.

        Args:
            instructions: Profile instructions with potential @mentions

        Returns:
            Tuple of (messages, resolved_paths):
            - messages: List of context messages from resolved mentions
            - resolved_paths: Set of all resolved file paths (for deduplication)
        """
        if not has_mentions(instructions):
            logger.debug("No mentions found in profile instructions")
            return [], set()

        logger.info("Resolving mentions from profile instructions")
        return self.loader.load_mentions_with_paths(
            text=instructions,
            relative_to=self.compiled_profile_dir,
        )

    def resolve_agents_md(self: "MentionResolver") -> list[ContextMessage]:
        """Resolve mentions from {project_path}/AGENTS.md.

        Returns:
            List of context messages, empty if file doesn't exist
        """
        agents_md = self.project_path / "AGENTS.md"

        if not agents_md.exists():
            logger.debug(f"AGENTS.md not found at {agents_md}")
            return []

        try:
            content = agents_md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to read AGENTS.md: {e}")
            return []

        if not has_mentions(content):
            logger.debug("No mentions found in AGENTS.md")
            return []

        logger.info(f"Resolving mentions from AGENTS.md at {agents_md}")
        return self.loader.load_mentions(
            text=content,
            relative_to=self.project_path,
        )

    def resolve_agents_md_chain(
        self: "MentionResolver",
        stop_at: Path | None = None,
        exclude_paths: set[Path] | None = None,
    ) -> list[ContextMessage]:
        """Resolve AGENTS.md from all ancestors up to stop_at (default: data_dir).

        Traverses from project_path up to stop_at, collecting AGENTS.md files.
        Checks {dir}/AGENTS.md and {dir}/.amplified/AGENTS.md at each level.
        Returns messages with ancestors first (most general), project last (most specific).

        Args:
            stop_at: Stop traversal at this directory (inclusive). Defaults to data_dir.
            exclude_paths: Set of resolved paths to skip (for deduplication with @mentions).

        Returns:
            List of context messages from all AGENTS.md files in ancestry chain.
        """
        exclude_paths = exclude_paths or set()
        stop_at = (stop_at or self.data_dir).resolve()
        paths: list[tuple[Path, Path]] = []
        current = self.project_path.resolve()

        # Collect all AGENTS.md paths from project up to stop_at
        while True:
            # Check for AGENTS.md in multiple locations (priority order)
            # 1. {dir}/AGENTS.md - direct file
            # 2. {dir}/.amplified/AGENTS.md - in .amplified subdirectory
            agents_md_locations = [
                current / "AGENTS.md",
                current / ".amplified" / "AGENTS.md",
            ]

            for agents_md in agents_md_locations:
                if agents_md.exists():
                    # Skip if already included via @mentions (deduplication)
                    if agents_md.resolve() in exclude_paths:
                        logger.debug(f"Skipping {agents_md} - already included via @mention")
                        break
                    paths.append((current, agents_md))
                    break  # Only include first match per directory

            # Stop if we've reached the boundary
            if current == stop_at:
                break

            # Stop if we've gone above the boundary (shouldn't happen normally)
            try:
                current.relative_to(stop_at)
            except ValueError:
                # current is not under stop_at, stop here
                break

            # Move to parent
            parent = current.parent
            if parent == current:
                # Reached filesystem root
                break
            current = parent

        # Process in reverse order (ancestors first, project last)
        messages: list[ContextMessage] = []
        for dir_path, agents_md in reversed(paths):
            try:
                content = agents_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {agents_md}: {e}")
                continue

            # Use full path for clarity in context label
            # Always include the AGENTS.md content itself
            messages.append(
                ContextMessage(
                    role="developer",
                    content=f"[Context from {agents_md}]\n\n{content}",
                )
            )

            # Additionally resolve any @mentions inside the file
            if has_mentions(content):
                loaded = self.loader.load_mentions(content, relative_to=dir_path)
                messages.extend(loaded)

        if paths:
            logger.info(
                f"Resolved {len(messages)} context messages from {len(paths)} AGENTS.md files in ancestry chain"
            )

        return messages

    def resolve_runtime_mentions(
        self: "MentionResolver",
        user_message: str,
    ) -> list[ContextMessage]:
        """Resolve @mentions from user message at runtime.

        NOTE: This method only resolves @mentions in the user's message.
        The ancestor AGENTS.md chain is resolved separately during session creation
        and stored in bundle_context_messages.json to avoid duplication.

        Args:
            user_message: User's message with potential @mentions

        Returns:
            List of context messages from resolved @mentions in user message
        """
        if not has_mentions(user_message):
            logger.debug("No mentions found in user message")
            return []

        logger.info("Resolving mentions from user message")
        return self.loader.load_mentions(
            text=user_message,
            relative_to=self.project_path,
        )
