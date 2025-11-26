"""Reference resolution service.

Resolves references (git URLs, fsspec paths, local paths) to local filesystem paths, supporting:
- git+ URLs: Clone/checkout to cache/git/{commit}/
- fsspec paths: Resolve to local path
- local paths: Validate and return resolved path
"""

import logging
import shutil
import uuid
from pathlib import Path

from git import Repo

from amplifier_library.storage.paths import get_cache_dir

logger = logging.getLogger(__name__)


class RefResolutionError(Exception):
    """Raised when reference resolution fails."""


class RefResolutionService:
    """Resolves references to local filesystem paths.

    Supports:
      - git+ URLs: Clone/checkout to cache/git/{commit}/
      - fsspec paths: Resolve to local path
      - local paths: Validate and return resolved path
    """

    def __init__(self, state_dir: Path):
        """Initialize with state directory for git checkouts.

        Args:
            state_dir: Path to state directory (for git checkouts)
        """
        self.state_dir = Path(state_dir)
        cache_dir = get_cache_dir()
        self.git_cache_dir = cache_dir / "git"
        self.git_cache_dir.mkdir(parents=True, exist_ok=True)
        self.fsspec_cache_dir = cache_dir / "fsspec"
        self.fsspec_cache_dir.mkdir(parents=True, exist_ok=True)

    def resolve_ref(self, source_ref: str) -> Path:
        """Resolve reference to local filesystem path.

        Supports multiple reference formats:
        - Git refs: git+https://github.com/org/repo@ref[/path]
          - With path: git+https://github.com/org/repo@main/tools/bash.py
          - Without path (repo root): git+https://github.com/org/repo@main
        - Absolute paths: /absolute/path/to/file.py
        - Fsspec paths: s3://bucket/path, http://example.com/file

        Args:
            source_ref: Source reference

        Returns:
            Path to reference content on local filesystem

        Side Effects:
            - Git clone/checkout to cache/git/{commit}/
            - May download remote fsspec resources

        Raises:
            RefResolutionError: If reference resolution fails

        Examples:
            >>> # Git ref with subpath
            >>> service.resolve_ref("git+https://github.com/org/repo@main/agents/agent.md")

            >>> # Git ref without path (resolves to repository root)
            >>> service.resolve_ref("git+https://github.com/microsoft/amplifier-module@main")

            >>> # Absolute path
            >>> service.resolve_ref("/home/user/agents/custom.md")
        """
        try:
            # Handle git+ refs
            if source_ref.startswith("git+"):
                # Parse: git+https://github.com/org/repo@ref/path/to/asset
                # Example: git+https://github.com/org/repo@main/agents/agent.md
                #          → repo: git+https://github.com/org/repo@main
                #          → asset_path: agents/agent.md

                # Validate that ref includes @ref_name (path after is optional)
                if "@" not in source_ref:
                    raise RefResolutionError(
                        f"Invalid git ref format (missing @ref): {source_ref}\n"
                        f"Expected format: git+https://github.com/org/repo@ref[/path/to/asset]"
                    )

                # Split on @ to get the base URL and the ref+path part
                base_url, ref_and_path = source_ref.rsplit("@", 1)

                # Check for #subdirectory= syntax - if present, pass entire thing to _fetch_git
                # _fetch_git handles subdirectory extraction correctly
                if "#subdirectory=" in ref_and_path or "#" in ref_and_path:
                    # _fetch_git handles subdirectory extraction
                    repo_ref = f"{base_url}@{ref_and_path}"
                    repo_path = self._fetch_git(repo_ref)
                    resolved = repo_path  # _fetch_git returns the subdirectory path
                else:
                    # Otherwise, handle the /path format for repo-relative paths
                    if "/" in ref_and_path:
                        ref_name, asset_path = ref_and_path.split("/", 1)
                    else:
                        # No path specified, use repository root
                        ref_name = ref_and_path
                        asset_path = "."

                    # Reconstruct the repo URL for fetching
                    repo_ref = f"{base_url}@{ref_name}"

                    # Fetch the repository (will use cache if available)
                    repo_path = self._fetch_git(repo_ref)

                    # Resolve the asset path within the repository
                    resolved = repo_path / asset_path

                if not resolved.exists():
                    raise RefResolutionError(
                        f"Asset not found at resolved path: {resolved}\n"
                        f"Original ref: {source_ref}\n"
                        f"Repository path: {repo_path}\n"
                        f"Asset path: {asset_path}"
                    )

                logger.debug(f"Resolved git ref {source_ref} → {resolved}")
                return resolved

            # Handle absolute paths
            if Path(source_ref).is_absolute():
                path = Path(source_ref)
                if not path.exists():
                    raise RefResolutionError(
                        f"Absolute path does not exist: {source_ref}\nThe path does not exist on the filesystem."
                    )
                logger.debug(f"Resolved absolute path {source_ref} → {path}")
                return path

            # Treat everything else as fsspec path
            return self._resolve_fsspec(source_ref)

        except RefResolutionError:
            # Re-raise RefResolutionError as-is
            raise
        except Exception as e:
            raise RefResolutionError(f"Failed to resolve reference {source_ref}: {e}") from e

    def _fetch_git(self, repo_url: str, ref: str = "main") -> Path:
        """Clone/checkout git repo to cache/git/{commit}/.

        Args:
            repo_url: Git repository URL (may include git+ prefix, @ref, and #subdirectory=path)
            ref: Git ref (branch, tag, commit) - overridden if URL contains @ref

        Returns:
            Path to cache/git/{commit-hash}/ or subdirectory within if #subdirectory= specified

        Side Effects:
            Git clone (shallow) if not cached

        Caching Strategy:
            - Commit hash used as cache key
            - If commit hash exists, return cached path
            - Otherwise, clone and cache
        """
        # Parse git+ URL format: git+https://github.com/org/repo@ref#subdirectory=path
        original_url = repo_url
        repo_url = repo_url.removeprefix("git+")

        # Extract subdirectory from URL if present
        subdirectory = None
        if "#subdirectory=" in repo_url:
            repo_url, subdir_part = repo_url.split("#subdirectory=", 1)
            subdirectory = subdir_part
        elif "#" in repo_url:
            repo_url, subdirectory = repo_url.split("#", 1)

        # Extract ref from URL if present
        if "@" in repo_url:
            repo_url, ref = repo_url.rsplit("@", 1)

        # Create temporary directory for clone
        temp_dir = self.git_cache_dir / f"temp_{uuid.uuid4().hex[:8]}"

        try:
            logger.info(f"Cloning {repo_url} ref={ref}" + (f" subdirectory={subdirectory}" if subdirectory else ""))

            # Shallow clone to get commit hash
            repo = Repo.clone_from(
                repo_url,
                temp_dir,
                branch=ref,
                depth=1,  # Shallow clone for speed
            )

            commit_hash = repo.head.commit.hexsha
            logger.debug(f"Git clone resulted in commit: {commit_hash}")

            # Build cache key including subdirectory if specified
            cache_key = commit_hash if not subdirectory else f"{commit_hash}_{subdirectory.replace('/', '_')}"
            cache_dir = self.git_cache_dir / cache_key

            # Check if already cached
            if cache_dir.exists():
                logger.info(f"Using cached ref: {cache_key}")
                shutil.rmtree(temp_dir)
                return cache_dir

            # If subdirectory specified, extract it
            if subdirectory:
                source_subdir = temp_dir / subdirectory
                if not source_subdir.exists():
                    shutil.rmtree(temp_dir)
                    raise RefResolutionError(
                        f"Subdirectory '{subdirectory}' not found in repository\n"
                        f"Repository URL: {repo_url}\n"
                        f"Git ref: {ref}\n"
                        f"Subdirectory: {subdirectory}"
                    )

                # Move subdirectory to cache location
                logger.info(f"Extracting subdirectory '{subdirectory}' to cache at {cache_key}")
                shutil.move(str(source_subdir), str(cache_dir))
                shutil.rmtree(temp_dir)
                return cache_dir

            # Move entire repo to cache location
            logger.info(f"Caching ref at {cache_key}")
            temp_dir.rename(cache_dir)
            return cache_dir

        except Exception as e:
            # Cleanup temp directory on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

            raise RefResolutionError(
                f"Git fetch failed for {original_url}\n"
                f"Repository URL: {repo_url}\n"
                f"Git ref: {ref}\n"
                f"Error: {e}\n\n"
                f"Troubleshooting:\n"
                f"  1. Check repository URL is correct\n"
                f"  2. Verify network connectivity\n"
                f"  3. Check authentication (if private repo)\n"
                f"  4. Try manual git clone: git clone {repo_url} -b {ref}"
            ) from e

    def _resolve_fsspec(self, fsspec_path: str) -> Path:
        """Resolve fsspec path to local path.

        Args:
            fsspec_path: Fsspec path (local, s3, http, etc.)

        Returns:
            Local path (may be cached if remote)

        Side Effects:
            May download remote resources to cache
        """
        import fsspec

        # For local paths, just return resolved path
        local_path = Path(fsspec_path)
        if local_path.exists():
            logger.info(f"Using local path: {local_path.resolve()}")
            return local_path.resolve()

        # For remote paths, use fsspec
        try:
            logger.info(f"Resolving fsspec path: {fsspec_path}")
            fs, path = fsspec.core.url_to_fs(fsspec_path)

            # Get filesystem protocol
            # Check protocol instead of isinstance to avoid type checking issues
            protocol = fs.protocol if isinstance(fs.protocol, str) else fs.protocol[0]

            # If local filesystem, return path
            if protocol == "file":
                resolved = Path(path)
                if not resolved.exists():
                    raise RefResolutionError(f"Local path does not exist: {resolved}")
                return resolved

            # If remote, cache locally
            protocol_cache_dir = self.fsspec_cache_dir / protocol
            protocol_cache_dir.mkdir(parents=True, exist_ok=True)

            # Download/sync to cache
            local_path = protocol_cache_dir / Path(path).name
            logger.info(f"Downloading {fsspec_path} to {local_path}")
            fs.get(path, str(local_path), recursive=True)

            if not local_path.exists():
                raise RefResolutionError(f"Failed to download from {fsspec_path}")

            return local_path

        except Exception as e:
            raise RefResolutionError(
                f"Fsspec resolution failed for {fsspec_path}\n"
                f"Error: {e}\n\n"
                f"Troubleshooting:\n"
                f"  1. Check path format is correct\n"
                f"  2. Verify network connectivity (if remote)\n"
                f"  3. Check authentication/credentials (if required)\n"
                f"  4. Ensure fsspec backend is installed (e.g., s3fs for s3://)"
            ) from e
