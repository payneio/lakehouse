"""Service for deduplicating file content by hash.

This module provides a deduplication service that tracks unique file content
and all paths where that content appears, preventing redundant context loading.
"""

import hashlib
from pathlib import Path

from amplifierd.models.context_messages import ContextFile


class ContentDeduplicator:
    """Deduplicates file content by hash, tracking all source paths.

    This service maintains a registry of unique file content identified by
    SHA-256 hash, allowing multiple paths with identical content to be
    represented by a single ContextFile with multiple source paths.

    Example:
        >>> dedup = ContentDeduplicator()
        >>> dedup.add_file(Path("file1.txt"), "content")
        >>> dedup.add_file(Path("file2.txt"), "content")
        >>> files = dedup.get_unique_files()
        >>> len(files)
        1
        >>> len(files[0].paths)
        2
    """

    def __init__(self: "ContentDeduplicator") -> None:
        """Initialize with empty state."""
        self._content_by_hash: dict[str, str] = {}
        self._paths_by_hash: dict[str, list[Path]] = {}

    def add_file(self: "ContentDeduplicator", path: Path, content: str) -> None:
        """Add file to deduplicator.

        If content with the same hash already exists, the path is added to
        the existing entry. Otherwise, a new entry is created.

        Args:
            path: Source filesystem path
            content: File content to deduplicate
        """
        content_hash = self._hash_content(content)

        if content_hash not in self._content_by_hash:
            self._content_by_hash[content_hash] = content
            self._paths_by_hash[content_hash] = []

        if path not in self._paths_by_hash[content_hash]:
            self._paths_by_hash[content_hash].append(path)

    def get_unique_files(self: "ContentDeduplicator") -> list[ContextFile]:
        """Get deduplicated files with all source paths.

        Returns:
            List of ContextFile objects, one per unique content hash
        """
        return [
            ContextFile(
                content=content,
                paths=self._paths_by_hash[content_hash],
                hash=content_hash,
            )
            for content_hash, content in self._content_by_hash.items()
        ]

    def get_known_hashes(self: "ContentDeduplicator") -> set[str]:
        """Return hashes currently tracked.

        Returns:
            Set of SHA-256 hashes for all tracked content
        """
        return set(self._content_by_hash.keys())

    @staticmethod
    def _hash_content(content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: String content to hash

        Returns:
            Hexadecimal digest of SHA-256 hash
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
