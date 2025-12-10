"""Git URL parsing utilities.

Shared logic for parsing git+ URL format across services.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedGitUrl:
    """Parsed components of a git+ URL.

    Attributes:
        url: Clean git URL without git+ prefix, @ref, or #subdirectory parts
        ref: Branch, tag, or commit reference (defaults to HEAD)
        subdirectory: Optional subdirectory path within repository
    """

    url: str
    ref: str = "HEAD"
    subdirectory: str | None = None


def parse_git_url(source: str) -> ParsedGitUrl:
    """Parse git+ URL format: git+https://github.com/org/repo@ref#subdirectory=path

    Handles all variations:
    - git+https://github.com/org/repo
    - git+https://github.com/org/repo@main
    - git+https://github.com/org/repo#subdirectory=path
    - git+https://github.com/org/repo@main#subdirectory=path

    Args:
        source: Git URL in git+ format

    Returns:
        ParsedGitUrl with extracted components

    Examples:
        >>> parse_git_url("git+https://github.com/user/repo@main#subdirectory=profiles")
        ParsedGitUrl(url='https://github.com/user/repo', ref='main', subdirectory='profiles')

        >>> parse_git_url("git+https://github.com/user/repo")
        ParsedGitUrl(url='https://github.com/user/repo', ref='HEAD', subdirectory=None)
    """
    # Strip git+ prefix
    url = source.removeprefix("git+")

    # Extract subdirectory from URL if present
    subdirectory = None
    if "#subdirectory=" in url:
        url, subdir_part = url.split("#subdirectory=", 1)
        subdirectory = subdir_part
    elif "#" in url:
        url, subdirectory = url.split("#", 1)

    # Extract ref from URL if present
    ref = "HEAD"
    if "@" in url:
        url, ref = url.rsplit("@", 1)

    return ParsedGitUrl(url=url, ref=ref, subdirectory=subdirectory)
