"""Hybrid @mention resolver combining bundle context and project files.

This resolver bridges amplifier-foundation's bundle @mention system with lakehouse's
project-specific @mention resolution. It handles two types of @mentions:

1. Bundle context @mentions (@namespace:path) - delegated to BaseMentionResolver
2. Project file @mentions (@path) - resolved against amplified_dir

This preserves lakehouse's innovation (project file integration) while using
amplifier-foundation for bundle context resolution.
"""

import logging
from pathlib import Path

from amplifier_foundation import Bundle
from amplifier_foundation.mentions import BaseMentionResolver
from amplifier_foundation.mentions.protocol import MentionResolverProtocol

from amplifierd.utils.mentions import has_mentions
from amplifierd.utils.mentions import parse_mentions

logger = logging.getLogger(__name__)


class HybridMentionResolver(MentionResolverProtocol):
    """Combines bundle @mentions with project file @mentions.

    This resolver preserves lakehouse's project file integration (@README.md) while
    using amplifier-foundation's bundle system for module and behavior context.

    Resolution priority:
    1. If @mention contains ':' → bundle context (e.g., @foundation:guidelines.md)
    2. Otherwise → project file (e.g., @README.md → amplified_dir/README.md)

    Security:
    - Project file @mentions are restricted to data_dir to prevent path traversal
    - Bundle @mentions are handled by amplifier-foundation's security
    """

    def __init__(
        self: "HybridMentionResolver",
        bundle: Bundle,
        amplified_dir: Path,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize hybrid resolver.

        Args:
            bundle: Prepared bundle for namespace resolution
            amplified_dir: Project directory for relative file resolution
            data_dir: Root data directory for security validation (defaults to amplified_dir.parent)
        """
        self.amplified_dir = amplified_dir.resolve()
        self.data_dir = (data_dir or amplified_dir.parent).resolve()

        # Bundle resolver for @namespace:path mentions
        self.bundle_resolver = BaseMentionResolver(
            bundles={bundle.name: bundle} if bundle.name else {},
            base_path=bundle.base_path or Path.cwd(),
        )

        logger.debug(f"HybridMentionResolver initialized: amplified_dir={amplified_dir}, data_dir={self.data_dir}")

    def resolve(self: "HybridMentionResolver", mention: str) -> Path | None:
        """Resolve @mention to file path.

        Args:
            mention: @mention string to resolve

        Returns:
            Resolved Path, or None if not found

        Resolution logic:
        - @namespace:path → delegate to bundle resolver
        - @path → resolve against amplified_dir with security validation
        """
        # Type 1: Bundle context (@namespace:path)
        if ":" in mention[1:]:
            logger.debug(f"Resolving bundle context mention: {mention}")
            return self.bundle_resolver.resolve(mention)

        # Type 2: Project file (@path)
        return self._resolve_project_file(mention)

    def _resolve_project_file(self: "HybridMentionResolver", mention: str) -> Path | None:
        """Resolve project file @mention against amplified_dir.

        Args:
            mention: @mention string (e.g., @README.md, @docs/guide.md)

        Returns:
            Resolved Path, or None if not found or security check fails

        Security:
        - Validates resolved path is within data_dir
        - Prevents path traversal attacks
        """
        path_str = mention.lstrip("@")
        resolved = (self.amplified_dir / path_str).resolve()

        # Security: Prevent path traversal outside data_dir
        try:
            resolved.relative_to(self.data_dir)
        except ValueError:
            logger.warning(
                f"Path traversal blocked: {mention} escapes data directory "
                f"(resolved: {resolved}, data_dir: {self.data_dir})"
            )
            return None

        if not resolved.exists():
            logger.debug(f"Project file not found: {resolved}")
            return None

        logger.debug(f"Resolved project file mention {mention} → {resolved}")
        return resolved

    def load_mentions(
        self: "HybridMentionResolver",
        text: str,
    ) -> list[tuple[str, Path]]:
        """Load all @mentions from text with recursive resolution.

        Args:
            text: Text containing @mentions

        Returns:
            List of (mention, resolved_path) tuples

        Note: This is a simplified interface for compatibility. For full
        deduplication and formatting, use amplifier-foundation's load_mentions.
        """
        results: list[tuple[str, Path]] = []
        visited: set[Path] = set()
        to_process = parse_mentions(text)

        while to_process:
            mention = to_process.pop(0)
            path = self.resolve(mention)

            if path is None:
                continue

            resolved = path.resolve()
            if resolved in visited:
                continue

            visited.add(resolved)
            results.append((mention, resolved))

            # Check for nested mentions
            try:
                content = resolved.read_text(encoding="utf-8")
                if has_mentions(content):
                    nested = parse_mentions(content)
                    to_process.extend(m for m in nested if m not in to_process)
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read {resolved}: {e}")

        return results
