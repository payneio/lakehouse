"""Utilities for parsing @mentions from text.

This module provides functions to extract and process @mentions while excluding
mentions found in code blocks and quoted strings.
"""

import re

# Pattern to match @mentions (excluding those embedded in alphanumeric text)
MENTION_PATTERN = re.compile(r"(?<![a-zA-Z0-9])@([a-zA-Z0-9_\-/\.:]+)")


def parse_mentions(text: str) -> list[str]:
    """Extract @mentions from text, excluding those in code blocks and quotes.

    This function filters out mentions that appear within:
    - Inline code blocks (enclosed in backticks)
    - Double-quoted strings
    - Single-quoted strings

    Args:
        text: The text to parse for @mentions

    Returns:
        List of @mention strings found (including the @ prefix)

    Example:
        >>> parse_mentions("See @file1.md and @file2.txt")
        ['@file1.md', '@file2.txt']
        >>> parse_mentions("Use `@code` not @real")
        ['@real']
    """
    # Filter out inline code (`...`)
    text_filtered = re.sub(r"`[^`\n]+`", "", text)
    # Filter out double quotes
    text_filtered = re.sub(r'"[^"\n]*"', "", text_filtered)
    # Filter out single quotes
    text_filtered = re.sub(r"'[^'\n]*'", "", text_filtered)

    # Extract mentions
    matches = MENTION_PATTERN.findall(text_filtered)
    return [f"@{m}" for m in matches if m != "mention"]  # Skip generic "@mention"


def extract_mention_path(mention: str) -> str:
    """Extract the path portion from an @mention string.

    Args:
        mention: An @mention string (e.g., "@file.md" or "@dir/file.txt")

    Returns:
        The path without the @ prefix

    Example:
        >>> extract_mention_path("@file.md")
        'file.md'
        >>> extract_mention_path("@dir/subdir/file.txt")
        'dir/subdir/file.txt'
    """
    return mention.lstrip("@")


def has_mentions(text: str) -> bool:
    """Check if text contains any @mentions.

    Args:
        text: The text to check

    Returns:
        True if @mentions are present, False otherwise

    Example:
        >>> has_mentions("See @file.md")
        True
        >>> has_mentions("No mentions here")
        False
    """
    return bool(MENTION_PATTERN.search(text))
