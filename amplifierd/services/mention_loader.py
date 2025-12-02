"""Service for loading files referenced by @mentions with recursive resolution.

This module provides the MentionLoader class which:
- Recursively resolves @mentions in text and loaded files
- Detects and prevents cycles using visited path tracking
- Deduplicates content across multiple @mentions
- Gracefully handles missing files
- Supports two @mention types:
  1. @context-key:path - Profile context references
  2. @path - Relative to amplified directory
"""

import logging
from pathlib import Path

from amplifierd.models.context_messages import ContextFile
from amplifierd.models.context_messages import ContextMessage
from amplifierd.services.content_deduplicator import ContentDeduplicator
from amplifierd.utils.mentions import has_mentions
from amplifierd.utils.mentions import parse_mentions

logger = logging.getLogger(__name__)


class MentionLoader:
    """Loads files referenced by @mentions with recursive resolution.

    Features:
    - Recursive loading (follows @mentions in loaded files)
    - Cycle detection (visited_paths set prevents infinite loops)
    - Content deduplication (same content = one message, all paths credited)
    - Graceful skip on missing files (logs warning, continues)

    Two @mention types:
    1. @context-key:path - Profile context references
       Resolves to: {compiled_profile_dir}/contexts/{context-key}/{path}
    2. @path - Relative to amplified directory
       Resolves to: {amplified_dir}/{path}
    """

    def __init__(
        self: "MentionLoader",
        compiled_profile_dir: Path,
        amplified_dir: Path,
    ) -> None:
        """Initialize loader with resolution paths.

        Args:
            compiled_profile_dir: Path to compiled profile (for context resolution)
            amplified_dir: Path to amplified directory (for relative resolution)
        """
        self.compiled_profile_dir = compiled_profile_dir
        self.amplified_dir = amplified_dir

    def load_mentions(
        self: "MentionLoader",
        text: str,
        relative_to: Path,
    ) -> list[ContextMessage]:
        """Load @mentions recursively with cycle detection and deduplication.

        Args:
            text: Text containing @mentions
            relative_to: Base path for updating relative resolution context

        Returns:
            List of ContextMessage objects (role="developer") for context injection

        Algorithm:
        1. Parse initial @mentions from text
        2. While mentions to process:
           a. Pop mention from queue
           b. Resolve to file path
           c. Skip if already visited (cycle detection)
           d. Load file content
           e. Add to deduplicator
           f. Parse nested @mentions from content
           g. Add new nested mentions to queue
        3. Get deduplicated files
        4. Create ContextMessage for each unique file
        """
        deduplicator = ContentDeduplicator()
        visited_paths: set[Path] = set()
        path_to_mention: dict[Path, str] = {}
        to_process: list[str] = parse_mentions(text)

        logger.debug(f"Starting mention loading with {len(to_process)} initial mentions")

        while to_process:
            mention = to_process.pop(0)
            logger.debug(f"Processing mention: {mention}")

            path = self._resolve_mention(mention, relative_to)

            if path is None:
                continue

            resolved_path = path.resolve()
            if resolved_path in visited_paths:
                logger.debug(f"Skipping already visited path: {resolved_path}")
                continue  # Cycle detection

            visited_paths.add(resolved_path)
            path_to_mention[resolved_path] = mention

            try:
                content = resolved_path.read_text(encoding="utf-8")
                logger.debug(f"Loaded {len(content)} bytes from {resolved_path}")
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {resolved_path}: {e}")
                continue

            deduplicator.add_file(resolved_path, content)

            # Parse nested mentions and add to queue
            if has_mentions(content):
                nested_mentions = parse_mentions(content)
                logger.debug(f"Found {len(nested_mentions)} nested mentions in {resolved_path}")
                for nested in nested_mentions:
                    if nested not in to_process and nested != mention:
                        to_process.append(nested)

        unique_files = deduplicator.get_unique_files()
        logger.debug(f"Resolved {len(unique_files)} unique files from mentions")

        return self._create_messages(unique_files, path_to_mention)

    def _resolve_mention(
        self: "MentionLoader",
        mention: str,
        relative_to: Path,
    ) -> Path | None:
        """Resolve @mention to file path.

        Two types:
        1. @context-key:path → {compiled_profile_dir}/contexts/{context-key}/{path}
        2. @path → {amplified_dir}/{path} (with security validation)

        Args:
            mention: The @mention string to resolve
            relative_to: Base path for relative resolution context

        Returns:
            Resolved file path, or None on resolution failure (graceful skip)
        """
        # Type 1: @context-key:path
        if ":" in mention[1:]:
            parts = mention[1:].split(":", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid context mention format: {mention}")
                return None

            context_key, path = parts

            # Resolve to PRE-COMPILED context directory
            context_dir = self.compiled_profile_dir / "contexts" / context_key

            if not context_dir.exists():
                logger.warning(f"Context '{context_key}' not found at {context_dir}")
                return None

            file_path = context_dir / path

            if not file_path.exists():
                logger.warning(f"Context file not found: {file_path}")
                return None

            logger.debug(f"Resolved context mention {mention} → {file_path}")
            return file_path

        # Type 2: @path (relative to amplified_dir)
        path_str = mention.lstrip("@")
        resolved = (self.amplified_dir / path_str).resolve()

        # Security: Prevent path traversal
        try:
            resolved.relative_to(self.amplified_dir.resolve())
        except ValueError:
            logger.warning(f"Path traversal blocked: {mention} escapes amplified_dir")
            return None

        if not resolved.exists():
            logger.debug(f"File not found: {resolved}")
            return None

        logger.debug(f"Resolved file mention {mention} → {resolved}")
        return resolved

    def _create_messages(
        self: "MentionLoader",
        context_files: list[ContextFile],
        path_to_mention: dict[Path, str],
    ) -> list[ContextMessage]:
        """Create ContextMessage objects from deduplicated files.

        Args:
            context_files: List of deduplicated ContextFile objects
            path_to_mention: Mapping from resolved paths to original @mention strings

        Returns:
            List of ContextMessage objects with formatted content

        Format: [Context from @mention → /path]\n\n{content}
        """
        messages = []

        for ctx_file in context_files:
            # Format paths with original @mention
            path_displays = []
            for p in ctx_file.paths:
                original_mention = path_to_mention.get(p)
                if original_mention:
                    path_displays.append(f"{original_mention} → {p}")
                else:
                    path_displays.append(str(p))

            paths_str = ", ".join(path_displays)
            content = f"[Context from {paths_str}]\n\n{ctx_file.content}"

            # Collect original mentions for source tracking
            source_mentions = [path_to_mention.get(p, "") for p in ctx_file.paths]

            messages.append(
                ContextMessage(
                    role="developer",
                    content=content,
                    source_mentions=source_mentions,
                )
            )

        return messages
