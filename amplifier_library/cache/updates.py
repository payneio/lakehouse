"""Update service for orchestrating cache updates.

Coordinates updates across RefResolution → Discovery → Compilation pipeline
with support for dry-run and force modes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

from .detection import ChangeDetectionService
from .metadata_store import MetadataStore
from .models import AllUpdateResult
from .models import CollectionUpdateResult
from .models import ProfileMetadata
from .models import ProfileUpdateResult

if TYPE_CHECKING:
    from amplifierd.services.collection_service import CollectionService
    from amplifierd.services.profile_compilation import ProfileCompilationService
    from amplifierd.services.profile_discovery import ProfileDiscoveryService
    from amplifierd.services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)


class UpdateService:
    """Service for orchestrating cache updates."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        change_detection: ChangeDetectionService,
        collection_service: CollectionService,
        ref_resolution_service: RefResolutionService,
        profile_discovery_service: ProfileDiscoveryService,
        profile_compilation_service: ProfileCompilationService,
    ) -> None:
        """Initialize update service.

        Args:
            metadata_store: Metadata store for persistent state
            change_detection: Change detection service
            collection_service: Collection management service
            ref_resolution_service: Reference resolution service
            profile_discovery_service: Profile discovery service
            profile_compilation_service: Profile compilation service
        """
        self.metadata_store = metadata_store
        self.change_detection = change_detection
        self.collection_service = collection_service
        self.ref_resolution = ref_resolution_service
        self.discovery = profile_discovery_service
        self.compilation = profile_compilation_service
        logger.info("Initialized UpdateService")

    async def update_collection(
        self,
        collection_id: str,
        check_only: bool = False,
        force: bool = False,
    ) -> CollectionUpdateResult:
        """Update collection if source changed.

        Args:
            collection_id: Collection to update
            check_only: If True, only check what would be updated
            force: If True, skip change detection and force update

        Returns:
            Collection update result
        """
        logger.info(f"Updating collection {collection_id} (check_only={check_only}, force={force})")

        try:
            # Get collection metadata
            collection = self.metadata_store.get_collection(collection_id)
            if not collection:
                return CollectionUpdateResult(
                    collection_id=collection_id,
                    success=False,
                    message=f"Collection not found: {collection_id}",
                    profile_results=[],
                    total_profiles=0,
                    successful_updates=0,
                    failed_updates=0,
                )

            # Check for changes (unless force mode)
            if not force:
                source_change = await self.change_detection.check_collection_source(collection_id)
                if not source_change:
                    logger.info(f"No changes detected in collection {collection_id}")
                    return CollectionUpdateResult(
                        collection_id=collection_id,
                        success=True,
                        message="No changes detected",
                        profile_results=[],
                        total_profiles=0,
                        successful_updates=0,
                        failed_updates=0,
                    )

            # Actually sync the collection (clone/update git repo)
            if not check_only:
                logger.info(f"Syncing collection {collection_id} from {collection.source_location}")
                try:
                    # Use RefResolutionService to clone/update the collection
                    # This handles git cloning and caching
                    resolved_path = self.ref_resolution.resolve_ref(collection.source_location)
                    logger.info(f"Collection synced to {resolved_path}")

                    # Update collection metadata
                    collection.last_updated = datetime.now(UTC)
                    collection.mount_path = resolved_path
                    # TODO: Get actual commit hash from git repo for tracking
                    self.metadata_store.save_collection(collection)

                    # Discover profiles from the synced collection
                    logger.info(f"Discovering profiles in collection {collection_id}")
                    discovered_profiles = self.discovery.discover_profiles(collection_id, resolved_path)
                    logger.info(f"Discovered {len(discovered_profiles)} profiles in {collection_id}")

                    # Compile each discovered profile
                    profile_results = []
                    for profile in discovered_profiles:
                        try:
                            logger.info(f"Compiling profile {collection_id}/{profile.name}")

                            # Compile the profile
                            compiled_path = self.compilation.compile_profile(
                                collection_id=collection_id,
                                profile=profile,
                                force=force,
                            )

                            # Calculate manifest hash
                            manifest_path = compiled_path / f"{profile.name}.md"
                            if manifest_path.exists():
                                with open(manifest_path, "rb") as f:
                                    manifest_hash = hashlib.sha256(f.read()).hexdigest()
                            else:
                                manifest_hash = ""

                            # Create/update profile metadata
                            profile_metadata = ProfileMetadata(
                                profile_id=profile.name,
                                collection_id=collection_id,
                                source_path=resolved_path,
                                cache_path=compiled_path,
                                source_modified=datetime.now(UTC),
                                cache_built=datetime.now(UTC),
                                manifest_hash=manifest_hash,
                                last_checked=datetime.now(UTC),
                            )
                            self.metadata_store.save_profile(profile_metadata)

                            profile_results.append(
                                ProfileUpdateResult(
                                    profile_id=profile.name,
                                    success=True,
                                    message="Successfully discovered and compiled",
                                    actions_taken=["discovered", "compiled"],
                                    cache_path=str(compiled_path),
                                    error=None,
                                )
                            )
                            logger.info(f"Successfully compiled {collection_id}/{profile.name}")

                        except Exception as e:
                            logger.error(f"Failed to compile profile {profile.name}: {e}")
                            profile_results.append(
                                ProfileUpdateResult(
                                    profile_id=profile.name,
                                    success=False,
                                    message=f"Compilation failed: {e}",
                                    actions_taken=["discovered"],
                                    cache_path=None,
                                    error=str(e),
                                )
                            )

                except Exception as e:
                    logger.error(f"Failed to sync collection {collection_id}: {e}")
                    return CollectionUpdateResult(
                        collection_id=collection_id,
                        success=False,
                        message=f"Failed to sync collection: {e}",
                        profile_results=[],
                        total_profiles=0,
                        successful_updates=0,
                        failed_updates=0,
                    )

            # Calculate summary
            successful = sum(1 for r in profile_results if r.success)
            failed = len(profile_results) - successful

            # Update collection metadata
            if not check_only and profile_results:
                collection.last_updated = datetime.now(UTC)
                collection.last_checked = datetime.now(UTC)
                self.metadata_store.save_collection(collection)

            return CollectionUpdateResult(
                collection_id=collection_id,
                success=failed == 0,
                message=f"Updated {successful}/{len(profile_results)} profiles",
                profile_results=profile_results,
                total_profiles=len(profile_results),
                successful_updates=successful,
                failed_updates=failed,
            )

        except Exception as e:
            logger.error(f"Error updating collection {collection_id}: {e}")
            return CollectionUpdateResult(
                collection_id=collection_id,
                success=False,
                message=f"Update failed: {e}",
                profile_results=[],
                total_profiles=0,
                successful_updates=0,
                failed_updates=0,
            )

    async def update_profile(
        self,
        collection_id: str,
        profile_id: str,
        check_only: bool = False,
        force: bool = False,
    ) -> ProfileUpdateResult:
        """Update profile if manifest or dependencies changed.

        Args:
            collection_id: Collection containing profile
            profile_id: Profile to update
            check_only: If True, only check what would be updated
            force: If True, skip change detection and force update

        Returns:
            Profile update result
        """
        logger.info(f"Updating profile {profile_id} (check_only={check_only}, force={force})")

        actions_taken: list[str] = []

        profile = self.metadata_store.get_profile(collection_id, profile_id)

        try:
            # Get profile metadata
            if not profile:
                # Profile not in metadata - try to discover it
                if check_only:
                    return ProfileUpdateResult(
                        profile_id=profile_id,
                        success=True,
                        message="Would discover and compile new profile",
                        actions_taken=["would-discover", "would-compile"],
                        cache_path=None,
                        error=None,
                    )

                # Discover profile - need to get collection path first
                collection = self.metadata_store.get_collection(collection_id)
                if not collection:
                    return ProfileUpdateResult(
                        profile_id=profile_id,
                        success=False,
                        message=f"Collection not found: {collection_id}",
                        actions_taken=[],
                        cache_path=None,
                        error="Collection not found",
                    )

                discovered_profiles = self.discovery.discover_profiles(
                    collection_id=collection_id,
                    collection_path=collection.mount_path,
                )

                # discovered_profiles returns ProfileDetails objects
                profile_detail = next(
                    (p for p in discovered_profiles if p.name == profile_id),
                    None,
                )

                if not profile_detail:
                    return ProfileUpdateResult(
                        profile_id=profile_id,
                        success=False,
                        message=f"Profile not found: {profile_id}",
                        actions_taken=[],
                        cache_path=None,
                        error="Profile not found in collection",
                    )

                # Create initial metadata (will be updated after compilation)
                # For now, use empty metadata - will be populated after compile
                actions_taken.append("discovered")

            # Check for changes (unless force mode)
            needs_update = force
            if not force and profile:
                # Check manifest change
                manifest_change = await self.change_detection.check_profile_manifest(
                    collection_id,
                    profile_id,
                )
                if manifest_change:
                    needs_update = True
                    actions_taken.append("manifest-changed")

                # Check dependency changes
                dep_changes = await self.change_detection.check_profile_dependencies(
                    collection_id,
                    profile_id,
                )
                if dep_changes:
                    needs_update = True
                    actions_taken.append(f"{len(dep_changes)}-dependencies-changed")

            if not needs_update and profile:
                logger.info(f"No changes detected for profile {profile_id}")
                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=True,
                    message="No changes detected",
                    actions_taken=["checked"],
                    cache_path=str(profile.cache_path) if profile.cache_path else None,
                    error=None,
                )

            if check_only:
                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=True,
                    message="Would recompile profile",
                    actions_taken=actions_taken + ["would-recompile"],
                    cache_path=None,
                    error=None,
                )

            # Get ProfileDetails for compilation - need to rediscover
            collection = self.metadata_store.get_collection(collection_id)
            if not collection:
                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=False,
                    message=f"Collection not found: {collection_id}",
                    actions_taken=actions_taken,
                    cache_path=None,
                    error="Collection not found",
                )

            discovered_profiles = self.discovery.discover_profiles(
                collection_id=collection_id,
                collection_path=collection.mount_path,
            )

            profile_detail = next(
                (p for p in discovered_profiles if p.name == profile_id),
                None,
            )

            if not profile_detail:
                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=False,
                    message=f"Profile {profile_id} not found in collection",
                    actions_taken=actions_taken,
                    cache_path=None,
                    error="Profile not found",
                )

            # Compile profile (includes ref resolution internally)
            logger.debug(f"Compiling profile {profile_id}")
            try:
                compiled_path = self.compilation.compile_profile(
                    collection_id=collection_id,
                    profile=profile_detail,
                    force=force,
                )
                actions_taken.append("compiled")

                # Ensure profile metadata exists - create if needed
                if not profile:
                    # Create metadata for newly discovered profile
                    manifest_path = compiled_path / "profile.yaml"
                    if manifest_path.exists():
                        with open(manifest_path, "rb") as f:
                            manifest_hash = hashlib.sha256(f.read()).hexdigest()
                    else:
                        manifest_hash = ""

                    profile = ProfileMetadata(
                        profile_id=profile_id,
                        collection_id=collection_id,
                        source_path=compiled_path.parent,
                        cache_path=compiled_path,
                        source_modified=datetime.now(UTC),
                        cache_built=datetime.now(UTC),
                        manifest_hash=manifest_hash,
                        last_checked=datetime.now(UTC),
                    )
                else:
                    # Update existing metadata
                    profile.cache_built = datetime.now(UTC)
                    profile.last_checked = datetime.now(UTC)
                    profile.cache_path = compiled_path

                    # Recalculate manifest hash
                    manifest_path = profile.source_path / "profile.yaml"
                    if manifest_path.exists():
                        with open(manifest_path, "rb") as f:
                            profile.manifest_hash = hashlib.sha256(f.read()).hexdigest()

                self.metadata_store.save_profile(profile)

                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=True,
                    message=f"Successfully updated: {', '.join(actions_taken)}",
                    actions_taken=actions_taken,
                    cache_path=str(profile.cache_path),
                    error=None,
                )

            except Exception as e:
                logger.error(f"Compilation failed for {profile_id}: {e}")
                return ProfileUpdateResult(
                    profile_id=profile_id,
                    success=False,
                    message=f"Compilation failed: {e}",
                    actions_taken=actions_taken,
                    cache_path=None,
                    error=str(e),
                )

        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {e}")
            return ProfileUpdateResult(
                profile_id=profile_id,
                success=False,
                message=f"Update failed: {e}",
                actions_taken=actions_taken,
                cache_path=None,
                error=str(e),
            )

    async def update_all(
        self,
        check_only: bool = False,
        force: bool = False,
    ) -> AllUpdateResult:
        """Update all collections and profiles.

        Args:
            check_only: If True, only check what would be updated
            force: If True, skip change detection and force update

        Returns:
            All update result
        """
        logger.info(f"Updating all collections (check_only={check_only}, force={force})")

        try:
            # Get all collections
            collections = self.metadata_store.list_collections()
            collection_results = []

            for collection in collections:
                result = await self.update_collection(
                    collection_id=collection.collection_id,
                    check_only=check_only,
                    force=force,
                )
                collection_results.append(result)

            # Calculate summary
            total_profiles = sum(r.total_profiles for r in collection_results)
            successful_updates = sum(r.successful_updates for r in collection_results)
            failed_updates = sum(r.failed_updates for r in collection_results)

            return AllUpdateResult(
                success=failed_updates == 0,
                message=f"Updated {successful_updates}/{total_profiles} profiles across {len(collection_results)} collections",
                collection_results=collection_results,
                total_collections=len(collection_results),
                total_profiles=total_profiles,
                successful_updates=successful_updates,
                failed_updates=failed_updates,
            )

        except Exception as e:
            logger.error(f"Error updating all collections: {e}")
            return AllUpdateResult(
                success=False,
                message=f"Update all failed: {e}",
                collection_results=[],
                total_collections=0,
                total_profiles=0,
                successful_updates=0,
                failed_updates=0,
            )
