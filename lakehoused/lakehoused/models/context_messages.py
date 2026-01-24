"""Data models for context message handling and file deduplication.

This module provides models for representing loaded context files and
formatted context messages used in the Amplified system.
"""

from pathlib import Path

from pydantic import BaseModel
from pydantic import Field


class ContextFile(BaseModel):
    """Represents a loaded context file with deduplication support.

    This model stores file content along with all paths where identical
    content was found, enabling efficient deduplication of repeated content.

    Attributes:
        content: The file's text content
        paths: All filesystem paths where this content was found
        hash: SHA-256 hash of the content for deduplication
    """

    content: str = Field(description="File content")
    paths: list[Path] = Field(description="All source paths with this content")
    hash: str = Field(description="SHA-256 content hash")


class ContextMessage(BaseModel):
    """Message containing loaded context from @mentions.

    This model represents a formatted message that includes context loaded
    from @mention references in user input.

    Attributes:
        role: Message role, always "developer" for context messages
        content: Formatted message content with path headers
        source_mentions: Original @mention strings that triggered loading
    """

    role: str = Field(default="developer", description="Message role")
    content: str = Field(description="Formatted message content")
    source_mentions: list[str] = Field(default_factory=list, description="Original @mentions")
