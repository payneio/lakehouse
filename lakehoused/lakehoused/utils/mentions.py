"""Utilities for parsing @mentions from text.

This module provides functions to extract and process @mentions while excluding
mentions found in code blocks and quoted strings.

Supports two mention formats:
1. Simple: @path/to/file.md (no spaces allowed)
2. Quoted: @"path with spaces/file.md" (spaces and special chars allowed)
"""

import re

# Pattern to match simple @mentions (excluding those embedded in alphanumeric text)
# Matches: @path/to/file.md, @context:path, etc.
SIMPLE_MENTION_PATTERN = re.compile(r"(?<![a-zA-Z0-9])@([a-zA-Z0-9_\-/\.:]+)")

# Pattern to match quoted @mentions (allows spaces and special characters)
# Matches: @"path with spaces.md", @"dir/file name.txt", etc.
# Note: This pattern must be applied BEFORE filtering out double quotes
QUOTED_MENTION_PATTERN = re.compile(r'(?<![a-zA-Z0-9])@"([^"]+)"')


def parse_mentions(text: str) -> list[str]:
    """Extract @mentions from text, excluding those in code blocks.

    Supports two formats:
    1. Simple: @path/to/file.md (no spaces)
    2. Quoted: @"path with spaces/file.md" (spaces allowed)

    This function filters out mentions that appear within:
    - Inline code blocks (enclosed in backticks)

    Note: Double-quoted strings are NOT filtered because @"..." is valid syntax.

    Args:
        text: The text to parse for @mentions

    Returns:
        List of @mention strings found (including the @ prefix)
        Quoted mentions are returned without quotes: @"file.md" -> @file.md

    Example:
        >>> parse_mentions("See @file1.md and @file2.txt")
        ['@file1.md', '@file2.txt']
        >>> parse_mentions('Use @"My Document.md" here')
        ['@My Document.md']
        >>> parse_mentions("Use `@code` not @real")
        ['@real']
    """
    # Filter out inline code (`...`) - these should never contain mentions
    text_filtered = re.sub(r"`[^`\n]+`", "", text)

    mentions: list[str] = []

    # First, extract quoted mentions (before we might filter quotes)
    # These can contain spaces and special characters
    quoted_matches = QUOTED_MENTION_PATTERN.findall(text_filtered)
    for match in quoted_matches:
        if match:  # Skip empty matches
            mentions.append(f"@{match}")

    # Remove quoted mentions from text to avoid double-matching the path part
    text_for_simple = QUOTED_MENTION_PATTERN.sub("", text_filtered)

    # Filter out remaining double quotes (not part of @"..." syntax)
    text_for_simple = re.sub(r'"[^"\n]*"', "", text_for_simple)
    # Filter out single quotes
    text_for_simple = re.sub(r"'[^'\n]*'", "", text_for_simple)

    # Extract simple mentions
    simple_matches = SIMPLE_MENTION_PATTERN.findall(text_for_simple)
    for match in simple_matches:
        if match and match != "mention":  # Skip generic "@mention"
            mentions.append(f"@{match}")

    return mentions


def extract_mention_path(mention: str) -> str:
    """Extract the path portion from an @mention string.

    Handles both simple and quoted formats:
    - @file.md -> file.md
    - @"My Document.md" -> My Document.md

    Args:
        mention: An @mention string (e.g., "@file.md" or '@"path with spaces.md"')

    Returns:
        The path without the @ prefix (and without quotes if quoted)

    Example:
        >>> extract_mention_path("@file.md")
        'file.md'
        >>> extract_mention_path("@dir/subdir/file.txt")
        'dir/subdir/file.txt'
        >>> extract_mention_path('@"My Document.md"')
        'My Document.md'
    """
    path = mention.lstrip("@")
    # Remove surrounding quotes if present
    if path.startswith('"') and path.endswith('"'):
        path = path[1:-1]
    return path


def has_mentions(text: str) -> bool:
    """Check if text contains any @mentions (simple or quoted).

    Args:
        text: The text to check

    Returns:
        True if @mentions are present, False otherwise

    Example:
        >>> has_mentions("See @file.md")
        True
        >>> has_mentions('See @"My File.md"')
        True
        >>> has_mentions("No mentions here")
        False
    """
    return bool(SIMPLE_MENTION_PATTERN.search(text) or QUOTED_MENTION_PATTERN.search(text))


def needs_quoting(path: str) -> bool:
    """Check if a path needs to be quoted for use in an @mention.

    Args:
        path: The file path to check

    Returns:
        True if the path contains characters that require quoting

    Example:
        >>> needs_quoting("file.md")
        False
        >>> needs_quoting("My Document.md")
        True
        >>> needs_quoting("path/with spaces/file.md")
        True
    """
    # Check if path contains any character not allowed in simple mentions
    return not bool(re.fullmatch(r"[a-zA-Z0-9_\-/\.:]+", path))


def format_mention(path: str) -> str:
    """Format a path as an @mention, quoting if necessary.

    Args:
        path: The file path to format

    Returns:
        Properly formatted @mention string

    Example:
        >>> format_mention("file.md")
        '@file.md'
        >>> format_mention("My Document.md")
        '@"My Document.md"'
    """
    if needs_quoting(path):
        return f'@"{path}"'
    return f"@{path}"
