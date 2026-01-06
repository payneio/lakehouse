"""Bundle loading service - replaces ProfileCompilationService."""

import logging
from pathlib import Path
from typing import Any

from amplifier_foundation import BundleRegistry
from amplifier_foundation import load_bundle
from amplifier_foundation.bundle import PreparedBundle

logger = logging.getLogger(__name__)


class BundleService:
    """Service for loading and preparing bundles for session creation."""

    def __init__(self, bundles_dir: Path, home_dir: Path):
        """
        Initialize the bundle service.

        Args:
            bundles_dir: Directory containing local bundle files (.md)
            home_dir: AMPLIFIER_HOME directory (contains cache/ and registry.json)
        """
        self.bundles_dir = bundles_dir
        self.home_dir = home_dir
        self.registry = BundleRegistry(home=home_dir)
        logger.info(f"BundleService initialized: bundles_dir={bundles_dir}, home={home_dir}")

    async def load_bundle(self, bundle_name: str) -> PreparedBundle:
        """
        Load and prepare a bundle for session creation.

        Args:
            bundle_name: Name of the bundle to load (e.g., "foundation/base", "test-minimal")

        Returns:
            PreparedBundle with modules activated and ready for session creation

        Raises:
            FileNotFoundError: If bundle not found locally or in registry
            Exception: If bundle loading or preparation fails
        """
        logger.info(f"Loading bundle: {bundle_name}")

        # Check local bundles first
        # Handle both flat (test-minimal.md) and nested (foundation/base.md) paths
        local_path = self.bundles_dir / f"{bundle_name}.md"
        if local_path.exists():
            logger.info(f"Loading bundle from local path: {local_path}")
            bundle = await load_bundle(str(local_path))
        else:
            # Try registry - pass bundle name explicitly to get single Bundle
            logger.info(f"Loading bundle from registry: {bundle_name}")
            result = await self.registry.load(bundle_name)

            # Registry.load() returns Bundle when name provided, dict when None
            # Type checker needs explicit assertion since it can't narrow union
            if isinstance(result, dict):
                raise TypeError(f"Expected Bundle, got dict (should not happen with name_or_uri={bundle_name})")
            bundle = result

        # Prepare (activate modules, resolve @mentions)
        logger.info(f"Preparing bundle: {bundle_name}")
        prepared = await bundle.prepare(install_deps=True)

        logger.info(f"Bundle prepared successfully: {bundle_name}")
        return prepared

    def get_mount_plan(self, prepared: PreparedBundle) -> dict[str, Any]:
        """
        Convert PreparedBundle to AmplifierSession mount plan format.

        The mount plan is the dict structure expected by AmplifierSession.initialize().

        Args:
            prepared: PreparedBundle with modules activated

        Returns:
            Mount plan dict compatible with AmplifierSession
        """
        logger.debug("Converting PreparedBundle to mount plan")

        # PreparedBundle.mount_plan already has the right structure!
        mount_plan = prepared.mount_plan

        logger.debug(
            f"Mount plan retrieved: {len(mount_plan.get('tools', []))} tools, {len(mount_plan.get('hooks', []))} hooks"
        )
        return mount_plan
