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

from amplifierd.models.context_messages import ContextMessage
from amplifierd.services.mention_loader import MentionLoader
from amplifierd.utils.mentions import has_mentions

logger = logging.getLogger(__name__)


class MentionResolver:
    """Resolves @mentions from various sources into context messages."""

    def __init__(
        self: "MentionResolver",
        compiled_profile_dir: Path,
        amplified_dir: Path,
        data_dir: Path | None = None,
        loader: MentionLoader | None = None,
    ) -> None:
        """Initialize resolver with context directories.

        Args:
            compiled_profile_dir: Path to compiled profile directory
            amplified_dir: Path to amplified directory (project root)
            data_dir: Path to data directory (for security validation). Defaults to amplified_dir.parent if not provided.
            loader: Optional MentionLoader instance (creates default if None)
        """
        self.compiled_profile_dir = compiled_profile_dir.resolve()
        self.amplified_dir = amplified_dir.resolve()
        self.data_dir = data_dir.resolve() if data_dir is not None else amplified_dir.parent.resolve()
        self.loader = loader or MentionLoader(
            compiled_profile_dir=self.compiled_profile_dir,
            amplified_dir=self.amplified_dir,
            data_dir=self.data_dir,
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
        if not has_mentions(instructions):
            logger.debug("No mentions found in profile instructions")
            return []

        logger.info("Resolving mentions from profile instructions")
        return self.loader.load_mentions(
            text=instructions,
            relative_to=self.compiled_profile_dir,
        )

    def resolve_agents_md(self: "MentionResolver") -> list[ContextMessage]:
        """Resolve mentions from {amplified_dir}/AGENTS.md.

        Returns:
            List of context messages, empty if file doesn't exist
        """
        agents_md = self.amplified_dir / "AGENTS.md"

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
            relative_to=self.amplified_dir,
        )

    def resolve_runtime_mentions(
        self: "MentionResolver",
        user_message: str,
    ) -> list[ContextMessage]:
        """Resolve mentions from user message at runtime.

        Combines AGENTS.md + user message mentions.

        Args:
            user_message: User's message with potential @mentions

        Returns:
            List of context messages (AGENTS.md first, then user mentions)
        """
        messages: list[ContextMessage] = []

        # First, resolve AGENTS.md mentions
        messages.extend(self.resolve_agents_md())

        # Then resolve user message mentions
        if has_mentions(user_message):
            logger.info("Resolving mentions from user message")
            user_mentions = self.loader.load_mentions(
                text=user_message,
                relative_to=self.amplified_dir,
            )
            messages.extend(user_mentions)
        else:
            logger.debug("No mentions found in user message")

        return messages
