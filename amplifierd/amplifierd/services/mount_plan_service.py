"""Mount plan service for compiling profiles on-demand (v3).

This service compiles profiles from source profile.yaml at session creation time.
Mount plans are generated in-memory and not persisted to profile directories.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class MountPlanService:
    """Service for compiling profiles on-demand from source profile.yaml (v3)."""

    def __init__(self, share_dir: Path) -> None:
        """Initialize mount plan service.

        Args:
            share_dir: Path to share directory (contains profiles)
        """
        self.share_dir = Path(share_dir)
        logger.info(f"MountPlanService initialized with share_dir={self.share_dir}")

    def generate_mount_plan(self, profile_id: str, amplified_dir: Path) -> dict[str, Any]:
        """Generate mount plan by compiling profile with session context.

        Args:
            profile_id: Profile identifier (e.g., "software-developer")
            amplified_dir: Absolute path to amplified directory for this session

        Returns:
            Compiled mount plan dictionary

        Raises:
            FileNotFoundError: If profile or profile.yaml not found
            ValueError: If profile compilation fails
        """
        from amplifier_library.services.registry_service import RegistryService
        from amplifier_library.storage import get_cache_dir
        from amplifierd.services.profile_compilation import ProfileCompilationService
        from amplifierd.services.ref_resolution import RefResolutionService

        logger.info(f"Compiling mount plan for profile: {profile_id}")

        # Find profile directory
        profile_dir = self.share_dir / "profiles" / profile_id
        if not profile_dir.exists():
            raise FileNotFoundError(f"Profile not found: {profile_id}")

        # Read profile.yaml source
        profile_yaml_path = profile_dir / "profile.yaml"

        if not profile_yaml_path.exists():
            # Backward compatibility: try mount_plan.json
            mount_plan_path = profile_dir / "mount_plan.json"
            if mount_plan_path.exists():
                logger.warning(
                    f"Using legacy mount_plan.json for profile '{profile_id}'. "
                    "Consider re-syncing from registry to get profile.yaml source."
                )
                mount_plan = json.loads(mount_plan_path.read_text())
                # Add session context to legacy mount_plan
                if "session" not in mount_plan:
                    mount_plan["session"] = {}
                if "settings" not in mount_plan["session"]:
                    mount_plan["session"]["settings"] = {}
                mount_plan["session"]["settings"]["amplified_dir"] = str(amplified_dir)
                mount_plan["session"]["settings"]["session_cwd"] = str(amplified_dir)
                mount_plan["session"]["settings"]["profile_name"] = profile_id
                return mount_plan

            raise FileNotFoundError(f"No profile.yaml or mount_plan.json for profile: {profile_id}")

        logger.debug(f"Loading profile.yaml from: {profile_yaml_path}")
        profile_yaml = yaml.safe_load(profile_yaml_path.read_text())
        config_yaml = {}  # Modern format has config inline

        # Initialize compilation service
        cache_dir = get_cache_dir()
        registry_service = RegistryService(share_dir=self.share_dir)
        ref_resolution = RefResolutionService(state_dir=cache_dir)
        compilation_service = ProfileCompilationService(
            share_dir=self.share_dir,
            cache_dir=cache_dir,
            ref_resolution=ref_resolution,
            registry_service=registry_service,
        )

        # Compile profile (creates mount_plan.json in profile directory)
        logger.debug(f"Compiling profile '{profile_id}' with session context")
        compiled_profile_dir = compilation_service.compile_profile(
            profile_id=profile_id, profile_yaml=profile_yaml, config_yaml=config_yaml
        )

        # Read the compiled mount_plan
        mount_plan_path = compiled_profile_dir / "mount_plan.json"
        mount_plan = json.loads(mount_plan_path.read_text())

        # Delete mount_plan.json from profile directory (it's for session only)
        if mount_plan_path.exists():
            logger.debug(f"Removing compiled mount_plan from profile directory: {mount_plan_path}")
            mount_plan_path.unlink()

        # Add session-specific context
        if "session" not in mount_plan:
            mount_plan["session"] = {}
        if "settings" not in mount_plan["session"]:
            mount_plan["session"]["settings"] = {}

        mount_plan["session"]["settings"]["amplified_dir"] = str(amplified_dir)
        mount_plan["session"]["settings"]["session_cwd"] = str(amplified_dir)
        mount_plan["session"]["settings"]["profile_name"] = profile_id

        logger.info(f"Mount plan compiled successfully for profile '{profile_id}'")
        return mount_plan
