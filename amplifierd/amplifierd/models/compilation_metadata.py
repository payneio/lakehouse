"""Compilation metadata for tracking profile compilation state."""

from dataclasses import dataclass


@dataclass
class ProfileCompilationMetadata:
    """Metadata tracking profile compilation state.

    Stored as .compilation_meta.json in compiled profile directory.
    Used for change detection to prevent unnecessary recompilation.

    Attributes:
        source_commit: Source commit hash when compiled (for git-backed profiles)
        manifest_hash: SHA256 of profile manifest (for change detection)
        compiled_at: ISO timestamp of compilation
    """

    source_commit: str
    manifest_hash: str
    compiled_at: str
