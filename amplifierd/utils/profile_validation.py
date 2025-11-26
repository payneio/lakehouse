"""Shared profile validation utilities."""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def is_valid_profile(profile_path: Path) -> bool:
    """Validate that file is a valid schema v2 profile.

    Full validation for profile files - checks for:
    - YAML frontmatter with proper structure
    - profile.name, profile.version fields
    - profile.schema_version == 2

    Args:
        profile_path: Path to profile file

    Returns:
        True if file is a valid schema v2 profile
    """
    try:
        with open(profile_path) as f:
            content = f.read()

        # Must have YAML frontmatter
        if not content.startswith("---"):
            logger.debug(f"Skipping {profile_path.name}: No YAML frontmatter found")
            return False

        # Split frontmatter from markdown content
        parts = content.split("---", 2)
        if len(parts) < 3:
            logger.debug(f"Skipping {profile_path.name}: Invalid frontmatter format")
            return False

        # Parse YAML
        try:
            data = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.debug(f"Skipping {profile_path.name}: Failed to parse YAML: {e}")
            return False

        # Validate required fields
        if not isinstance(data, dict):
            logger.debug(f"Skipping {profile_path.name}: Frontmatter must be a dictionary")
            return False

        profile = data.get("profile", {})
        if not isinstance(profile, dict):
            logger.debug(f"Skipping {profile_path.name}: No 'profile' section")
            return False

        # Check for required fields
        has_name = "name" in profile
        has_version = "version" in profile

        if not (has_name and has_version):
            logger.debug(f"Skipping {profile_path.name}: Missing name or version")
            return False

        # Validate schema version (must be 2)
        schema_version = profile.get("schema_version")
        if schema_version is None:
            logger.debug(f"Skipping {profile_path.name}: Missing schema_version (v2 required)")
            return False

        if schema_version != 2:
            logger.debug(f"Skipping {profile_path.name}: schema_version {schema_version} not supported (v2 required)")
            return False

        return True

    except Exception as e:
        logger.debug(f"Error validating {profile_path.name}: {e}")
        return False
