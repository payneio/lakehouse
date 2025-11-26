"""Profile compilation service.

Resolves profile refs and caches compiled assets for dynamic import.
Creates Python module structure from profile manifests with all refs resolved.
"""

import logging
import shutil
from pathlib import Path

from amplifierd.models.profiles import ProfileDetails
from amplifierd.services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)


class RefResolutionError(Exception):
    """Raised when ref resolution fails."""


class ProfileCompilationError(Exception):
    """Raised when profile compilation fails."""


class ProfileCompilationService:
    """Compiles profiles by resolving all refs and caching assets.

    Creates Python module structure for dynamic import with all referenced
    assets (agents, context, modules) fetched and organized into a standard
    directory layout.

    Compiled Structure:
        share/profiles/{collection-id}/{profile-name}/
          {profile-name}.md  (manifest from discovery)
          orchestrator/
            __init__.py
            (orchestrator files)
          agents/
            __init__.py
            agent1.md
          context/
            __init__.py
            doc1.md
          tools/
            __init__.py
          hooks/
            __init__.py
          providers/
            __init__.py
    """

    def __init__(self, share_dir: Path, ref_resolution: RefResolutionService):
        """Initialize with share directory and ref resolution service.

        Args:
            share_dir: Path to share directory (compiled profiles go here)
            ref_resolution: RefResolutionService for resolving refs
        """
        self.share_dir = Path(share_dir)
        self.profiles_dir = self.share_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.ref_resolution = ref_resolution

    def compile_profile(self, collection_id: str, profile: ProfileDetails) -> Path:
        """Compile profile by resolving all refs.

        Creates a staging directory for compilation, resolves all referenced
        assets (agents, context, module sources), and creates a Python module
        structure ready for dynamic import. On success, atomically renames
        staging to final location. On failure, cleans up staging directory.

        Args:
            collection_id: Collection identifier
            profile: ProfileDetails with refs to resolve

        Returns:
            Path to compiled profile directory (share/profiles/{collection}/{profile-name}/)

        Side Effects:
            - Fetches and caches all referenced assets via RefResolutionService
            - Creates Python module structure with __init__.py files
            - Copies resolved assets into compilation directory
            - Uses staging directory for atomic compilation

        Raises:
            RefResolutionError: If any ref cannot be resolved
            ProfileCompilationError: If compilation fails

        Atomicity Guarantee:
            Uses staging directory pattern - final compilation directory only
            exists if ALL assets resolved successfully. No partial state on failure.

        Example:
            >>> service = ProfileCompilationService(share_dir, ref_resolution)
            >>> compiled_path = service.compile_profile("mycollection", profile)
            >>> print(compiled_path)
            /path/to/share/profiles/mycollection/general/
        """
        logger.info(f"Compiling profile {collection_id}/{profile.name}")

        # Define final and staging paths (using profile name, not random UID)
        final_dir = self.profiles_dir / collection_id / profile.name
        staging_dir = self.profiles_dir / collection_id / f".staging-{profile.name}"

        # Create staging directory
        staging_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created staging directory: {staging_dir}")

        try:
            # Initialize assets dictionary for all module types
            assets: dict[str, list[Path]] = {
                "orchestrator": [],
                "agents": [],
                "context": [],
                "tools": [],
                "hooks": [],
                "providers": [],
            }

            # Resolve orchestrator module source (if present)
            if profile.session and profile.session.orchestrator.source:
                resolved_path = self._resolve_ref(profile.session.orchestrator.source, "orchestrator")
                assets["orchestrator"].append(resolved_path)
                logger.debug(f"Resolved orchestrator: {profile.session.orchestrator.module}")

            # Resolve context-manager module source (if present)
            if profile.session and profile.session.context_manager and profile.session.context_manager.source:
                resolved_path = self._resolve_ref(profile.session.context_manager.source, "context-manager")
                assets["orchestrator"].append(resolved_path)
                logger.debug(f"Resolved context-manager: {profile.session.context_manager.module}")

            # Resolve agent refs (schema v2: list of file refs)
            if profile.agents:
                logger.debug(f"Resolving {len(profile.agents)} agent refs")
                for agent_ref in profile.agents:
                    try:
                        resolved_path = self._resolve_ref(agent_ref, "agent")
                        assets["agents"].append(resolved_path)
                        logger.debug(f"Resolved agent: {agent_ref}")
                    except RefResolutionError as e:
                        logger.error(f"Failed to resolve agent ref '{agent_ref}': {e}")
                        raise

            # Resolve context refs (schema v2: list of directory refs)
            if profile.context:
                logger.debug(f"Resolving {len(profile.context)} context directory refs")
                for context_ref in profile.context:
                    try:
                        resolved_path = self._resolve_ref(context_ref, "context")

                        # Verify it's a directory
                        if not resolved_path.is_dir():
                            raise RefResolutionError(
                                f"Context ref must be a directory: {context_ref}\nResolved to: {resolved_path}"
                            )

                        assets["context"].append(resolved_path)
                        logger.debug(f"Resolved context directory: {context_ref}")
                    except RefResolutionError as e:
                        logger.error(f"Failed to resolve context ref '{context_ref}': {e}")
                        raise

            # Resolve tool module sources
            for tool in profile.tools:
                if tool.source:
                    resolved_path = self._resolve_ref(tool.source, "tool")
                    assets["tools"].append(resolved_path)

            # Resolve hook module sources
            for hook in profile.hooks:
                if hook.source:
                    resolved_path = self._resolve_ref(hook.source, "hook")
                    assets["hooks"].append(resolved_path)

            # Resolve provider module sources
            for provider in profile.providers:
                if provider.source:
                    resolved_path = self._resolve_ref(provider.source, "provider")
                    assets["providers"].append(resolved_path)

            # Create Python module structure in STAGING directory
            self._create_module_structure(staging_dir, assets)

            # Copy the cached manifest file from discovery cache into staging
            # The manifest is preserved by the discovery service and must exist in the final compiled profile
            manifest_source = self.profiles_dir / collection_id / profile.name / f"{profile.name}.md"
            if manifest_source.exists():
                manifest_dest = staging_dir / f"{profile.name}.md"
                shutil.copy2(manifest_source, manifest_dest)
                logger.debug(f"Copied profile manifest to staging: {profile.name}.md")
            else:
                logger.warning(f"Profile manifest not found in discovery cache: {manifest_source}")

            # Atomic rename: staging -> final (only happens if we got here without exception)
            # Remove existing directory if present (profiles are fully regenerated on sync)
            if final_dir.exists():
                logger.debug(f"Removing existing directory: {final_dir}")
                shutil.rmtree(final_dir)
            logger.debug(f"Compilation successful, atomically renaming {staging_dir} -> {final_dir}")
            staging_dir.rename(final_dir)

            logger.info(f"Successfully compiled profile: {collection_id}/{profile.name} → {final_dir}")
            return final_dir

        except Exception as e:
            # Cleanup staging directory on failure - no partial state left behind
            logger.error(f"Compilation failed for {collection_id}/{profile.name}: {e}")
            if staging_dir.exists():
                logger.debug(f"Cleaning up staging directory: {staging_dir}")
                shutil.rmtree(staging_dir)
            raise ProfileCompilationError(f"Failed to compile profile {profile.name}: {e}") from e

    def _resolve_ref(self, ref: str, ref_type: str) -> Path:
        """Resolve reference with profile-specific error context.

        Args:
            ref: Reference string (git+URL, absolute path, fsspec)
            ref_type: Type of ref for error messages (agent, context, module)

        Returns:
            Path to resolved asset

        Raises:
            RefResolutionError: If resolution fails with profile context
        """
        try:
            return self.ref_resolution.resolve_ref(ref)
        except RefResolutionError as e:
            raise RefResolutionError(f"Failed to resolve {ref_type} reference '{ref}': {e}") from e

    def _create_module_structure(self, target_dir: Path, assets: dict[str, list[Path]]) -> None:
        """Create Python module structure for compiled profile.

        Creates a standard Python package layout with subdirectories for each
        asset type, __init__.py files, and copies all resolved assets into place.

        Args:
            target_dir: Compilation target directory
            assets: Dict mapping asset type to list of asset paths

        Side Effects:
            - Creates target_dir/__init__.py
            - Creates subdirectories with __init__.py for each asset type
            - Copies files and directories from resolved asset paths

        Structure Created:
            target_dir/
              __init__.py
              orchestrator/
                __init__.py
                (orchestrator files)
              agents/
                __init__.py
                agent1.md
              context/
                __init__.py
                doc1.md
              tools/
                __init__.py
              hooks/
                __init__.py
              providers/
                __init__.py
        """
        # Create root __init__.py
        root_init = target_dir / "__init__.py"
        root_init.write_text('"""Compiled profile module."""\n')
        logger.debug(f"Created {root_init}")

        # Create subdirectory for each asset type
        for asset_type, asset_paths in assets.items():
            if not asset_paths:
                # Still create empty directories for consistency
                type_dir = target_dir / asset_type
                type_dir.mkdir(exist_ok=True)

                # Create __init__.py
                init_file = type_dir / "__init__.py"
                init_file.write_text(f'"""{asset_type.capitalize()} assets."""\n')
                logger.debug(f"Created empty {asset_type}/ directory")
                continue

            # Create asset type directory
            type_dir = target_dir / asset_type
            type_dir.mkdir(exist_ok=True)

            # Create __init__.py
            init_file = type_dir / "__init__.py"
            init_file.write_text(f'"""{asset_type.capitalize()} assets."""\n')

            # Copy assets
            for asset_path in asset_paths:
                if asset_path.is_file():
                    # Copy single file
                    dest = type_dir / asset_path.name
                    shutil.copy2(asset_path, dest)
                    logger.debug(f"Copied file {asset_path.name} to {type_dir}/")

                elif asset_path.is_dir():
                    # Copy entire directory, excluding non-essential directories
                    dest = type_dir / asset_path.name

                    def ignore_non_essential(dir: str, files: list[str]) -> set[str]:
                        """Ignore .git, __pycache__, .venv, and other non-essential directories."""
                        return {name for name in files if name in {".git", "__pycache__", ".venv", "node_modules"}}

                    shutil.copytree(asset_path, dest, dirs_exist_ok=True, ignore=ignore_non_essential)
                    logger.debug(f"Copied directory {asset_path.name}/ to {type_dir}/ (excluding .git and cache dirs)")

                else:
                    logger.warning(f"Asset path is neither file nor directory: {asset_path}")

            logger.debug(f"Created {asset_type}/ with {len(asset_paths)} assets")

        logger.info(f"Created Python module structure at {target_dir}")
