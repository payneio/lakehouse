"""Bundle registry parsing from BUNDLES.txt.

Parses bundle name-to-URI mappings for registration with Foundation's BundleRegistry.
Foundation handles git cloning/caching - we just provide the registry mappings.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


DEFAULT_BUNDLES_TXT = """\
# Amplifier Foundation bundles
# Format: name:git+https://github.com/owner/repo@branch#subdirectory=path/to/bundle.md
# Note: Fragment format follows pip/uv standard with subdirectory= prefix
#
# Foundation handles git cloning/caching to ~/.amplifier/cache/
# This preserves full repo structure for namespace:path resolution
#
# Foundation namespace (required for namespace:path includes like foundation:behaviors/logging)
foundation:git+https://github.com/microsoft/amplifier-foundation@main
amplifier-dev:git+https://github.com/microsoft/amplifier-foundation@main#subdirectory=bundles/amplifier-dev.yaml
minimal:git+https://github.com/microsoft/amplifier-foundation@main#subdirectory=bundles/minimal.yaml

# Personal bundles (payneio/payne-amplifier)
# payne-amplifier namespace (required for namespace:path includes like payne-amplifier:behaviors/software-development)
payne-amplifier:git+https://github.com/payneio/payne-amplifier@main
software-developer:git+https://github.com/payneio/payne-amplifier@main#subdirectory=bundles/software-developer.md
basic:git+https://github.com/payneio/payne-amplifier@main#subdirectory=bundles/basic.md
"""


def ensure_bundles_file(bundles_file: Path) -> None:
    """Create BUNDLES.txt with defaults if it doesn't exist.

    Args:
        bundles_file: Path to BUNDLES.txt file.
    """
    if not bundles_file.exists():
        bundles_file.parent.mkdir(parents=True, exist_ok=True)
        bundles_file.write_text(DEFAULT_BUNDLES_TXT)
        logger.info(f"Created default BUNDLES.txt at {bundles_file}")


def parse_bundles_file(bundles_file: Path) -> dict[str, str]:
    """Parse BUNDLES.txt and return name->URI mappings.

    Does NOT download files. The URIs are registered directly with
    Foundation's BundleRegistry, which handles git cloning/caching.

    Args:
        bundles_file: Path to BUNDLES.txt file.

    Returns:
        Dict mapping bundle name to git+ URI.
    """
    bundles: dict[str, str] = {}

    for line in bundles_file.read_text().splitlines():
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue

        # Parse name:git_ref format
        if ":" not in line:
            logger.warning(f"Invalid BUNDLES.txt line (missing ':'): {line}")
            continue

        try:
            name, git_ref = line.split(":", 1)
            name = name.strip()
            git_ref = git_ref.strip()

            if not name or not git_ref:
                logger.warning(f"Invalid BUNDLES.txt line (empty name or ref): {line}")
                continue

            bundles[name] = git_ref
        except ValueError:
            logger.warning(f"Invalid BUNDLES.txt line: {line}")
            continue

    return bundles


def add_bundle_entry(bundles_file: Path, name: str, git_url: str) -> None:
    """Add a new bundle entry to BUNDLES.txt.

    Args:
        bundles_file: Path to BUNDLES.txt file.
        name: Bundle name (kebab-case).
        git_url: Git URL (e.g., git+https://github.com/owner/repo@branch#subdirectory=path).

    Raises:
        ValueError: If bundle name already exists or URL is invalid.
    """
    # Ensure file exists
    ensure_bundles_file(bundles_file)

    # Parse existing bundles to check for duplicates
    existing = parse_bundles_file(bundles_file)
    if name in existing:
        raise ValueError(f"Bundle already exists: {name}")

    # Validate git URL format
    if not git_url.startswith("git+"):
        raise ValueError("Git URL must start with 'git+' (e.g., git+https://github.com/...)")

    # Append the new entry
    content = bundles_file.read_text()
    if not content.endswith("\n"):
        content += "\n"
    content += f"{name}:{git_url}\n"
    bundles_file.write_text(content)

    logger.info(f"Added bundle entry: {name}:{git_url}")


def remove_bundle_entry(bundles_file: Path, name: str) -> None:
    """Remove a bundle entry from BUNDLES.txt.

    Args:
        bundles_file: Path to BUNDLES.txt file.
        name: Bundle name to remove.

    Raises:
        ValueError: If bundle name not found.
    """
    if not bundles_file.exists():
        raise ValueError(f"Bundle not found: {name}")

    # Parse to verify it exists
    existing = parse_bundles_file(bundles_file)
    if name not in existing:
        raise ValueError(f"Bundle not found: {name}")

    # Rebuild the file without the removed entry
    lines = bundles_file.read_text().splitlines()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        # Keep comments and empty lines
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        # Check if this is the entry to remove
        if ":" in stripped:
            entry_name = stripped.split(":", 1)[0].strip()
            if entry_name == name:
                continue  # Skip this entry
        new_lines.append(line)

    bundles_file.write_text("\n".join(new_lines) + "\n")
    logger.info(f"Removed bundle entry: {name}")
