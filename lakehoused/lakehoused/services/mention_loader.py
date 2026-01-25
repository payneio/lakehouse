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

from lakehoused.models.context_messages import ContextFile
from lakehoused.models.context_messages import ContextMessage
from lakehoused.services.content_deduplicator import ContentDeduplicator
from lakehoused.utils.mentions import has_mentions
from lakehoused.utils.mentions import parse_mentions

logger = logging.getLogger(__name__)


class MentionLoader:
    """Loads files referenced by @mentions with recursive resolution.

    Features:
    - Recursive loading (follows @mentions in loaded files)
    - Cycle detection (visited_paths set prevents infinite loops)
    - Content deduplication (same content = one message, all paths credited)
    - Graceful skip on missing files (logs warning, continues)

    Three @mention types:
    1. @namespace:path - Bundle namespace references (e.g., @foundation:context/file.md)
       Resolves to: {source_base_paths[namespace]}/{path}
    2. @context-key:path - Profile context references
       Resolves to: {compiled_profile_dir}/contexts/{context-key}/{path}
    3. @path - Relative to amplified directory
       Resolves to: {project_path}/{path}
    """

    def __init__(
        self: "MentionLoader",
        compiled_profile_dir: Path,
        project_path: Path,
        data_dir: Path | None = None,
        source_base_paths: dict[str, Path] | None = None,
    ) -> None:
        """Initialize loader with resolution paths.

        Args:
            compiled_profile_dir: Path to compiled profile (for context resolution)
            project_path: Path to project directory (for relative resolution)
            data_dir: Path to data directory (for security validation). Defaults to project_path.parent if not provided.
            source_base_paths: Dict mapping bundle namespace to base_path for @namespace:path resolution.
                Enables @foundation:context/file.md to resolve to Foundation bundle's context directory.
        """
        self.compiled_profile_dir = compiled_profile_dir
        self.project_path = project_path
        self.data_dir = data_dir if data_dir is not None else project_path.parent
        self.source_base_paths = source_base_paths or {}

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
        messages, _ = self.load_mentions_with_paths(text, relative_to)
        return messages

    def load_mentions_with_paths(
        self: "MentionLoader",
        text: str,
        relative_to: Path,
    ) -> tuple[list[ContextMessage], set[Path]]:
        """Load @mentions and return both messages and resolved paths.

        Same as load_mentions() but also returns the set of resolved paths,
        useful for deduplication when the same file might be loaded from
        multiple sources (e.g., @mentions and ancestor AGENTS.md chain).

        Args:
            text: Text containing @mentions
            relative_to: Base path for updating relative resolution context

        Returns:
            Tuple of (messages, resolved_paths):
            - messages: List of ContextMessage objects
            - resolved_paths: Set of all resolved file paths (for deduplication)
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

        messages = self._create_messages(unique_files, path_to_mention)
        return messages, visited_paths

    def _resolve_mention(
        self: "MentionLoader",
        mention: str,
        relative_to: Path,
    ) -> Path | None:
        """Resolve @mention to file path with context-aware resolution.

        Three types (in priority order):
        1. @namespace:path → Bundle namespace resolution (e.g., @foundation:context/file.md)
           Resolves using source_base_paths if namespace is known
        2. @context-key:path → Context-aware resolution based on source file location
           If source file is in behaviors/{behavior_id}/ → Try behavior context first
           Always fallback to session/contexts/ if not found
        3. @path → {project_path}/{path} (with security validation)

        Args:
            mention: The @mention string to resolve
            relative_to: Path of file being parsed (determines resolution context)

        Returns:
            Resolved file path, or None on resolution failure (graceful skip)
        """
        # Type 1 & 2: @namespace:path or @context-key:path
        if ":" in mention[1:]:
            parts = mention[1:].split(":", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid namespaced mention format: {mention}")
                return None

            namespace, path_part = parts

            # Type 1: Check bundle source_base_paths first (for @foundation:context/... style)
            if namespace in self.source_base_paths:
                resolved = self.source_base_paths[namespace] / path_part
                if resolved.exists():
                    logger.debug(f"Resolved bundle namespace mention {mention} → {resolved}")
                    return resolved
                logger.debug(f"Bundle namespace path not found: {resolved}")
                # Don't return None yet - fall through to context-key resolution
                # in case this is actually a context-key that matches a namespace

            # Type 2: @context-key:path (fall through from namespace check)
            # Reuse already-parsed parts: namespace becomes context_key, path_part becomes path
            context_key, path = namespace, path_part

            # Determine if we're parsing a behavior file
            behavior_id = self._extract_behavior_id(relative_to)

            # Build search paths in priority order
            search_paths = []

            if behavior_id:
                # Try behavior-specific context first
                behavior_context = (
                    self.compiled_profile_dir / "behaviors" / behavior_id / "contexts" / context_key / path
                )
                search_paths.append(("behavior", behavior_context))

            # Try session-level context (new structure)
            session_context = self.compiled_profile_dir / "session" / "contexts" / context_key / path
            search_paths.append(("session", session_context))

            # Fallback: Legacy structure without session/ subdirectory
            legacy_context = self.compiled_profile_dir / "contexts" / context_key / path
            search_paths.append(("legacy", legacy_context))

            # Try each path in order
            for source_type, file_path in search_paths:
                if file_path.exists():
                    logger.debug(f"Resolved context mention {mention} from {source_type} → {file_path}")
                    return file_path

                # Backward compatibility: Try stripping 'context/' prefix
                if path.startswith("context/"):
                    fallback_path = path[len("context/") :]
                    fallback_file = file_path.parent.parent / fallback_path
                    if fallback_file.exists():
                        logger.debug(
                            f"Resolved context mention {mention} from {source_type} "
                            f"(stripped 'context/' prefix) → {fallback_file}"
                        )
                        return fallback_file

            logger.warning(f"Context file not found for {mention} (searched {len(search_paths)} locations)")
            return None

        # Type 3: @path (relative to project_path)
        path_str = mention.lstrip("@")
        resolved = (self.project_path / path_str).resolve()

        # Security: Prevent path traversal outside data_dir
        try:
            resolved.relative_to(self.data_dir.resolve())
        except ValueError:
            logger.warning(
                f"Path traversal blocked: {mention} escapes data directory "
                f"(resolved: {resolved}, data_dir: {self.data_dir})"
            )
            return None

        if not resolved.exists():
            logger.debug(f"File not found: {resolved}")
            return None

        logger.debug(f"Resolved file mention {mention} → {resolved}")
        return resolved

    def _extract_behavior_id(self: "MentionLoader", file_path: Path) -> str | None:
        """Extract behavior_id from file path if file is within a behavior directory.

        Args:
            file_path: Path of file being parsed

        Returns:
            behavior_id if file is in behaviors/{behavior_id}/, None otherwise

        Example:
            /profiles/basic/behaviors/web/agents/search.md → "web"
            /profiles/basic/session/agents/main.md → None
        """
        try:
            # Try to get relative path from compiled_profile_dir
            relative = file_path.relative_to(self.compiled_profile_dir)
            parts = relative.parts

            # Check if path is: behaviors/{behavior_id}/...
            if len(parts) >= 2 and parts[0] == "behaviors":
                return parts[1]

            return None
        except ValueError:
            # file_path is not within compiled_profile_dir
            return None

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
