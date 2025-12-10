"""Change detection service for cache invalidation.

Detects changes in collection sources, profile manifests, and profile dependencies
to determine when caches need to be invalidated and rebuilt.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from amplifier_library.utils.git_url import parse_git_url

from .metadata_store import MetadataStore
from .models import ChangeReport
from .models import DependencyChange
from .models import ManifestChange
from .models import SourceChange

if TYPE_CHECKING:
    from amplifierd.services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)


class ChangeDetectionService:
    """Service for detecting changes in collections and profiles."""

    def __init__(
        self,
        metadata_store: MetadataStore,
        ref_resolution_service: RefResolutionService,
    ) -> None:
        """Initialize change detection service.

        Args:
            metadata_store: Metadata store for cached state
            ref_resolution_service: Service for resolving profile dependencies
        """
        self.metadata_store = metadata_store
        self.ref_resolution_service = ref_resolution_service
        logger.info("Initialized ChangeDetectionService")

    async def check_collection_source(self, collection_id: str) -> SourceChange | None:
        """Check if collection source has changed.

        For git sources, checks if remote HEAD differs from cached commit.
        For local sources, checks if source directory modified time changed.

        Args:
            collection_id: Collection to check

        Returns:
            SourceChange if source changed, None otherwise
        """
        collection = self.metadata_store.get_collection(collection_id)
        if not collection:
            logger.warning(f"Collection not found in metadata: {collection_id}")
            return None

        try:
            if collection.source_type == "git":
                return await self._check_git_source(collection)
            if collection.source_type in ["local", "registry"]:
                return await self._check_local_source(collection)
            logger.warning(f"Unknown source type: {collection.source_type}")
            return None
        except Exception as e:
            logger.error(f"Error checking collection source {collection_id}: {e}")
            return None

    async def _check_git_source(self, collection) -> SourceChange | None:
        """Check if git source has new commits.

        Args:
            collection: Collection metadata

        Returns:
            SourceChange if remote HEAD differs from cached commit
        """
        try:
            # Parse git URL using shared utility
            parsed = parse_git_url(collection.source_location)

            logger.debug(f"Parsed git URL: {parsed.url}, ref: {parsed.ref}")

            # Run git ls-remote to get current commit
            proc = await asyncio.create_subprocess_exec(
                "git",
                "ls-remote",
                parsed.url,
                parsed.ref,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"git ls-remote failed for {parsed.url} ref {parsed.ref}: {error_msg}")
                return None

            # Parse output: "commit_hash\tref"
            output = stdout.decode().strip()
            if not output:
                logger.warning(f"Empty git ls-remote output for {parsed.url} ref {parsed.ref}")
                return None

            remote_commit = output.split()[0]

            # Compare with cached commit
            if remote_commit != collection.source_commit:
                logger.info(
                    f"Git source changed for {collection.collection_id}: "
                    f"{collection.source_commit[:8] if collection.source_commit else 'None'} -> {remote_commit[:8]}"
                )
                return SourceChange(
                    path=collection.mount_path,
                    change_type="modified",
                    old_mtime=collection.last_updated,
                    new_mtime=datetime.now(),
                )

            logger.debug(f"Git source unchanged for {collection.collection_id}: {remote_commit[:8]}")
            return None

        except Exception as e:
            logger.error(f"Error checking git source for {collection.collection_id}: {e}")
            return None

    async def _check_local_source(self, collection) -> SourceChange | None:
        """Check if local source directory has changed.

        Uses HTTP HEAD request for remote sources, filesystem stat for local.

        Args:
            collection: Collection metadata

        Returns:
            SourceChange if source modified time changed
        """
        try:
            source_location = collection.source_location

            # Handle file:// URLs
            if source_location.startswith("file://"):
                source_path = Path(source_location[7:])
                if not source_path.exists():
                    logger.warning(f"Local source not found: {source_path}")
                    return None

                # Check directory modification time
                current_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=UTC)
                if collection.last_updated and current_mtime > collection.last_updated:
                    logger.info(f"Local source changed: {source_path}")
                    return SourceChange(
                        path=source_path,
                        change_type="modified",
                        old_mtime=collection.last_updated,
                        new_mtime=current_mtime,
                    )
                return None

            # Handle HTTP(S) URLs - use HEAD request
            if source_location.startswith(("http://", "https://")):
                async with httpx.AsyncClient() as client:
                    response = await client.head(source_location, follow_redirects=True)
                    if response.status_code != 200:
                        logger.warning(f"HTTP HEAD failed for {source_location}: {response.status_code}")
                        return None

                    # Check ETag or Last-Modified headers
                    etag = response.headers.get("etag")
                    last_modified = response.headers.get("last-modified")

                    # For simplicity, treat any response as potentially changed
                    # (proper implementation would cache and compare ETags/Last-Modified)
                    logger.debug(f"HTTP source check: ETag={etag}, Last-Modified={last_modified}")
                    return None

            logger.warning(f"Unsupported source location format: {source_location}")
            return None

        except Exception as e:
            logger.error(f"Error checking local source: {e}")
            return None

    async def check_profile_manifest(
        self,
        collection_id: str,
        profile_id: str,
    ) -> ManifestChange | None:
        """Check if profile manifest has changed.

        Compares current manifest hash with cached hash.

        Args:
            collection_id: Collection containing profile
            profile_id: Profile to check

        Returns:
            ManifestChange if manifest hash differs
        """
        profile = self.metadata_store.get_profile(collection_id, profile_id)
        if not profile:
            logger.warning(f"Profile not found in metadata: {profile_id}")
            return None

        try:
            # Read current manifest file
            manifest_path = profile.source_path / "profile.yaml"
            if not manifest_path.exists():
                logger.warning(f"Profile manifest not found: {manifest_path}")
                return None

            # Calculate current hash
            with open(manifest_path, "rb") as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()

            # Compare with cached hash
            if current_hash != profile.manifest_hash:
                logger.info(f"Profile manifest changed: {profile_id}")
                return ManifestChange(
                    profile_id=profile_id,
                    field="manifest",
                    old_value=profile.manifest_hash[:8],
                    new_value=current_hash[:8],
                )

            logger.debug(f"Profile manifest unchanged: {profile_id}")
            return None

        except Exception as e:
            logger.error(f"Error checking profile manifest {profile_id}: {e}")
            return None

    async def check_profile_dependencies(
        self,
        collection_id: str,
        profile_id: str,
    ) -> list[DependencyChange]:
        """Check if profile dependencies have changed.

        Re-resolves dependencies and compares with cached dependencies.

        Args:
            collection_id: Collection containing profile
            profile_id: Profile to check

        Returns:
            List of dependency changes detected
        """
        changes: list[DependencyChange] = []

        try:
            # Get cached dependencies
            cached_deps = self.metadata_store.get_dependencies(collection_id, profile_id)

            # Re-resolve dependencies (simplified - would need actual profile manifest)
            profile = self.metadata_store.get_profile(collection_id, profile_id)
            if not profile:
                logger.warning(f"Profile not found: {profile_id}")
                return changes

            # For now, we'll just check if cached dependencies still exist
            # A full implementation would re-parse the manifest and resolve refs
            for dep in cached_deps:
                # Extract collection_id from dependency_profile_id (format: collection_id/profile_id)
                dep_collection_id = (
                    dep.dependency_profile_id.split("/")[0] if "/" in dep.dependency_profile_id else collection_id
                )
                dep_profile = self.metadata_store.get_profile(dep_collection_id, dep.dependency_profile_id)
                if not dep_profile:
                    changes.append(
                        DependencyChange(
                            dependent_profile_id=profile_id,
                            dependency_profile_id=dep.dependency_profile_id,
                            change_type="removed",
                        )
                    )
                elif dep_profile.is_stale:
                    changes.append(
                        DependencyChange(
                            dependent_profile_id=profile_id,
                            dependency_profile_id=dep.dependency_profile_id,
                            change_type="modified",
                        )
                    )

            if changes:
                logger.info(f"Found {len(changes)} dependency changes for {profile_id}")

            return changes

        except Exception as e:
            logger.error(f"Error checking profile dependencies {profile_id}: {e}")
            return changes

    async def detect_all_changes(
        self,
        collection_id: str,
        profile_id: str | None = None,
    ) -> ChangeReport:
        """Detect all changes for a profile or entire collection.

        Args:
            collection_id: Collection to check
            profile_id: Optional specific profile to check (if None, checks all)

        Returns:
            Complete change report
        """
        source_changes: list[SourceChange] = []
        manifest_changes: list[ManifestChange] = []
        dependency_changes: list[DependencyChange] = []

        try:
            # Check collection source
            source_change = await self.check_collection_source(collection_id)
            if source_change:
                source_changes.append(source_change)

            # Get profiles to check
            if profile_id:
                profiles = [self.metadata_store.get_profile(collection_id, profile_id)]
            else:
                profiles = self.metadata_store.list_profiles(collection_id)

            # Check each profile
            for profile in profiles:
                if not profile:
                    continue

                # Check manifest
                manifest_change = await self.check_profile_manifest(
                    collection_id,
                    profile.profile_id,
                )
                if manifest_change:
                    manifest_changes.append(manifest_change)

                # Check dependencies
                dep_changes = await self.check_profile_dependencies(
                    collection_id,
                    profile.profile_id,
                )
                dependency_changes.extend(dep_changes)

            report = ChangeReport(
                collection_id=collection_id,
                source_changes=source_changes,
                manifest_changes=manifest_changes,
                dependency_changes=dependency_changes,
                detected_at=datetime.now(),
            )

            logger.info(
                f"Change detection complete: {len(source_changes)} source, "
                f"{len(manifest_changes)} manifest, {len(dependency_changes)} dependency changes"
            )

            return report

        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
            return ChangeReport(
                collection_id=collection_id,
                source_changes=[],
                manifest_changes=[],
                dependency_changes=[],
                detected_at=datetime.now(),
            )
