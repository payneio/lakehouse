"""Bundle-based profile service for listing and managing bundles."""

import logging
import shutil
from pathlib import Path

from ..models import ProfileDetails
from ..models import ProfileInfo

logger = logging.getLogger(__name__)


class BundleProfileService:
    """Service for managing bundles as profiles."""

    def __init__(self, bundles_dir: Path):
        """Initialize bundle profile service.

        Args:
            bundles_dir: Directory containing bundle .md files
        """
        self.bundles_dir = bundles_dir
        self.bundles_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized BundleProfileService with bundles_dir: {bundles_dir}")

    def list_profiles(self) -> list[ProfileInfo]:
        """List all available bundles as profiles.

        Returns:
            List of profile information from bundle files
        """
        profiles = []

        if not self.bundles_dir.exists():
            logger.warning(f"Bundles directory does not exist: {self.bundles_dir}")
            return profiles

        # Find all .md files in bundles directory
        for bundle_path in self.bundles_dir.rglob("*.md"):
            # Get relative path from bundles_dir to create profile name
            relative_path = bundle_path.relative_to(self.bundles_dir)
            # Remove .md extension and convert path separators to forward slashes
            profile_name = str(relative_path.with_suffix("")).replace("\\", "/")

            profiles.append(
                ProfileInfo(
                    name=profile_name,
                    source="local",
                    source_type="local",
                    is_active=False,  # Bundle system doesn't track active profile
                )
            )

        logger.info(f"Found {len(profiles)} bundle profiles")
        return profiles

    def _extract_description(self, bundle_path: Path) -> str | None:
        """Extract description from bundle frontmatter.

        Args:
            bundle_path: Path to bundle .md file

        Returns:
            Description from bundle metadata, or None if not found
        """
        try:
            content = bundle_path.read_text(encoding="utf-8")

            # Bundle frontmatter is between --- markers
            if not content.startswith("---"):
                return None

            # Find closing --- marker
            end_marker = content.find("\n---\n", 3)
            if end_marker == -1:
                return None

            # Extract frontmatter (between the --- markers)
            frontmatter = content[3:end_marker]

            # Simple YAML parsing for description field
            for line in frontmatter.split("\n"):
                line = line.strip()
                if line.startswith("description:"):
                    # Extract description value (handle quoted strings)
                    desc = line[12:].strip()
                    if desc.startswith('"') and desc.endswith('"') or desc.startswith("'") and desc.endswith("'"):
                        desc = desc[1:-1]
                    return desc

            return None

        except Exception as e:
            logger.warning(f"Failed to extract description from {bundle_path}: {e}")
            return None

    def get_profile(self, name: str) -> ProfileDetails:
        """Get profile details by name.

        Args:
            name: Profile name (e.g., "foundation/base")

        Returns:
            Profile details

        Raises:
            FileNotFoundError: If bundle file not found
        """
        bundle_path = self.bundles_dir / f"{name}.md"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {name}")

        description = self._extract_description(bundle_path)

        return ProfileDetails(
            name=name,
            version="1.0.0",  # Default version for bundles
            description=description or f"Bundle profile: {name}",
            source="local",
            source_type="local",
            is_active=False,  # Bundle system doesn't track active profile
            providers=[],  # Bundle details not needed for basic profile info
            tools=[],
            hooks=[],
            agents={},
        )

    def get_bundle_content(self, name: str) -> str:
        """Get raw bundle markdown content.

        Args:
            name: Bundle name (e.g., "foundation/base")

        Returns:
            Bundle markdown content

        Raises:
            FileNotFoundError: If bundle file not found
        """
        bundle_path = self.bundles_dir / f"{name}.md"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {name}")

        return bundle_path.read_text(encoding="utf-8")

    def get_bundle_data(self, name: str) -> dict:
        """Get bundle data in structured format.

        Args:
            name: Bundle name (e.g., "foundation/base")

        Returns:
            Bundle data as dict matching Bundle dataclass fields

        Raises:
            FileNotFoundError: If bundle file not found
            ValueError: If bundle content cannot be parsed
        """
        import yaml

        bundle_path = self.bundles_dir / f"{name}.md"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {name}")

        content = bundle_path.read_text(encoding="utf-8")

        # Parse frontmatter and instruction
        if content.startswith("---"):
            end_marker = content.find("\n---\n", 3)
            if end_marker != -1:
                frontmatter_str = content[4:end_marker]
                try:
                    data = yaml.safe_load(frontmatter_str)
                except yaml.YAMLError as e:
                    raise ValueError(f"Failed to parse YAML frontmatter: {e}")

                instruction = content[end_marker + 5 :].strip()

                # Extract bundle data from frontmatter
                if "bundle" in data:
                    bundle_data = data["bundle"]
                    bundle_data["instruction"] = instruction
                    return bundle_data
                raise ValueError("Bundle frontmatter missing 'bundle' key")
            raise ValueError("Bundle frontmatter not properly closed with ---")
        raise ValueError("Bundle file missing frontmatter")

    def _bundle_to_markdown(self, bundle_data: dict) -> str:
        """Convert bundle data to markdown format with YAML frontmatter.

        Args:
            bundle_data: Bundle data dict matching Bundle dataclass fields

        Returns:
            Markdown string with YAML frontmatter
        """
        import yaml

        # Extract instruction (markdown body)
        instruction = bundle_data.pop("instruction", None) or ""

        # Create YAML frontmatter
        frontmatter = yaml.dump({"bundle": bundle_data}, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Combine frontmatter and instruction
        return f"---\n{frontmatter}---\n\n{instruction}"

    def create_bundle(self, bundle_data: dict) -> ProfileDetails:
        """Create a new bundle from structured data.

        Args:
            bundle_data: Bundle data dict matching Bundle dataclass fields

        Returns:
            Created bundle details

        Raises:
            ValueError: If bundle already exists or name is invalid
        """
        name = bundle_data.get("name")
        if not name:
            raise ValueError("Bundle name is required")

        # Validate name (alphanumeric, hyphens, slashes for subdirectories)
        if not all(c.isalnum() or c in "-/_" for c in name):
            raise ValueError(f"Invalid bundle name: {name}. Use only letters, numbers, hyphens, and slashes.")

        bundle_path = self.bundles_dir / f"{name}.md"

        if bundle_path.exists():
            raise ValueError(f"Bundle already exists: {name}")

        # Create parent directories if needed
        bundle_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to markdown and write
        markdown_content = self._bundle_to_markdown(dict(bundle_data))
        bundle_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"Created bundle: {name}")

        return self.get_profile(name)

    def update_bundle(self, name: str, bundle_data: dict) -> ProfileDetails:
        """Update an existing bundle with structured data.

        Args:
            name: Bundle name
            bundle_data: Partial bundle data dict with fields to update

        Returns:
            Updated bundle details

        Raises:
            FileNotFoundError: If bundle not found
        """
        import yaml

        bundle_path = self.bundles_dir / f"{name}.md"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {name}")

        # Read existing bundle content
        existing_content = bundle_path.read_text(encoding="utf-8")

        # Parse existing frontmatter
        if existing_content.startswith("---"):
            end_marker = existing_content.find("\n---\n", 3)
            if end_marker != -1:
                frontmatter_str = existing_content[4:end_marker]
                existing_data = yaml.safe_load(frontmatter_str)
                existing_instruction = existing_content[end_marker + 5 :]
            else:
                existing_data = {}
                existing_instruction = existing_content
        else:
            existing_data = {}
            existing_instruction = existing_content

        # Get bundle data from frontmatter
        bundle_config = existing_data.get("bundle", {})

        # Merge updates into existing bundle config
        for key, value in bundle_data.items():
            if value is not None:  # Only update non-None values
                bundle_config[key] = value

        # Preserve instruction if not provided in update
        if "instruction" not in bundle_data or bundle_data.get("instruction") is None:
            bundle_config["instruction"] = existing_instruction

        # Convert updated bundle to markdown
        markdown_content = self._bundle_to_markdown(bundle_config)
        bundle_path.write_text(markdown_content, encoding="utf-8")
        logger.info(f"Updated bundle: {name}")

        return self.get_profile(name)

    def copy_bundle(self, source_name: str, new_name: str) -> ProfileDetails:
        """Copy a bundle to a new name.

        Args:
            source_name: Source bundle name
            new_name: New bundle name

        Returns:
            New bundle details

        Raises:
            FileNotFoundError: If source bundle not found
            ValueError: If target bundle already exists
        """
        source_path = self.bundles_dir / f"{source_name}.md"

        if not source_path.exists():
            raise FileNotFoundError(f"Source bundle not found: {source_name}")

        # Validate new name
        if not all(c.isalnum() or c in "-/_" for c in new_name):
            raise ValueError(f"Invalid bundle name: {new_name}. Use only letters, numbers, hyphens, and slashes.")

        target_path = self.bundles_dir / f"{new_name}.md"

        if target_path.exists():
            raise ValueError(f"Bundle already exists: {new_name}")

        # Create parent directories if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy bundle file
        shutil.copy2(source_path, target_path)
        logger.info(f"Copied bundle {source_name} to {new_name}")

        return self.get_profile(new_name)

    def delete_bundle(self, name: str) -> None:
        """Delete a bundle.

        Args:
            name: Bundle name

        Raises:
            FileNotFoundError: If bundle not found
        """
        bundle_path = self.bundles_dir / f"{name}.md"

        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle not found: {name}")

        # Delete bundle file
        bundle_path.unlink()
        logger.info(f"Deleted bundle: {name}")

        # Clean up empty parent directories
        try:
            parent = bundle_path.parent
            while parent != self.bundles_dir and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass  # Directory not empty or permission issue
