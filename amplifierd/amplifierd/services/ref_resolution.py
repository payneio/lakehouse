"""Reference resolution service.

Resolves references (git URLs, fsspec paths, local paths) to local filesystem paths, supporting:
- git+ URLs: Clone/checkout to cache/git/{commit}/
- fsspec paths: Resolve to local path
- local paths: Validate and return resolved path
"""

import hashlib
import logging
import shutil
import urllib.parse
import uuid
from pathlib import Path

from amplifier_library.storage.paths import get_cache_dir
from amplifier_library.utils.git_url import parse_git_url
from git import Repo

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

            # Handle HTTP(S) URLs
            if source_ref.startswith(("https://", "http://")):
                return self._resolve_http_url(source_ref)

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
        # Parse git+ URL using shared utility
        parsed = parse_git_url(repo_url)
        original_url = repo_url  # Save original before overwriting
        repo_url = parsed.url
        ref = parsed.ref
        subdirectory = parsed.subdirectory

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

    def _resolve_http_url(self, url: str) -> Path:
        """Download HTTP(S) URL to cache.

        Args:
            url: HTTP(S) URL to download

        Returns:
            Path to cached file

        Raises:
            RefResolutionError: If download fails
        """
        import fsspec

        logger.info(f"Downloading URL: {url}")

        try:
            # Use fsspec to download
            fs, path = fsspec.core.url_to_fs(url)

            # Setup cache directory
            cache_dir = self.fsspec_cache_dir / "http"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Extract original filename from URL
            original_name = self._extract_name_from_url(url)
            final_path = cache_dir / original_name
            temp_path = cache_dir / f".tmp_{original_name}"

            # Return cached file if it exists
            if final_path.exists():
                logger.debug(f"Cache hit for {url} → {final_path}")
                return final_path

            # Download to temp path then atomically rename
            logger.info(f"Downloading {url} to cache")
            try:
                fs.get_file(path, str(temp_path))
                temp_path.rename(final_path)
                logger.info(f"Cached to: {final_path}")
            except Exception:
                shutil.rmtree(temp_path, ignore_errors=True)
                raise

            return final_path

        except Exception as e:
            raise RefResolutionError(f"Failed to resolve HTTP URL '{url}': {type(e).__name__}: {e}") from e

    def _generate_cache_key(self, url: str) -> str:
        """Generate 8-character hash from normalized URL.

        Args:
            url: Any fsspec-compatible URL

        Returns:
            8-character hex hash of normalized URL
        """
        parsed = urllib.parse.urlparse(url)

        if parsed.scheme in ("", "file"):
            normalized = str(Path(parsed.path).resolve())
        else:
            normalized = self._normalize_remote_url(parsed)

        return hashlib.sha256(normalized.encode()).hexdigest()[:8]

    def _normalize_remote_url(self, parsed: urllib.parse.ParseResult) -> str:
        """Normalize remote URL to canonical form.

        Args:
            parsed: Parsed URL components

        Returns:
            Normalized URL string
        """
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
            netloc = netloc.rsplit(":", 1)[0]

        path = parsed.path.rstrip("/")

        query = ""
        if parsed.query:
            params = sorted(urllib.parse.parse_qsl(parsed.query))
            query = urllib.parse.urlencode(params)

        return urllib.parse.urlunparse((scheme, netloc, path, "", query, ""))

    def _extract_name_from_url(self, url: str) -> str:
        """Extract original filename or directory name from URL.

        Args:
            url: fsspec-compatible URL

        Returns:
            Original filename or directory name, or "content" as fallback

        Examples:
            >>> _extract_name_from_url("http://site.com/agents/researcher.md")
            'researcher.md'
            >>> _extract_name_from_url("s3://bucket/agents/")
            'agents'
            >>> _extract_name_from_url("file:///data/foo.txt")
            'foo.txt'
        """
        parsed = urllib.parse.urlparse(url)
        path = Path(parsed.path.rstrip("/"))
        return path.name if path.name else "content"

    def _resolve_fsspec(self, fsspec_path: str) -> Path:
        """Resolve fsspec URL using hash-based cache with atomic writes.

        Cache miss downloads to .tmp_{name}, then atomically renames to preserve
        original filename/directory name and prevent partial download corruption.

        Args:
            fsspec_path: Any fsspec-compatible URL (file://, http://, s3://, etc.)

        Returns:
            Path to local cached content (file or directory) with original name preserved

        Raises:
            RuntimeError: If download fails
        """
        import fsspec

        # Only check for local paths if it doesn't look like a URL
        if not fsspec_path.startswith(("https://", "http://", "s3://", "gs://", "az://", "file://")):
            local_path = Path(fsspec_path)
            if local_path.exists():
                logger.info(f"Using local path: {local_path.resolve()}")
                return local_path.resolve()

        try:
            logger.info(f"Resolving fsspec path: {fsspec_path}")
            fs, path = fsspec.core.url_to_fs(fsspec_path)

            protocol = fs.protocol if isinstance(fs.protocol, str) else fs.protocol[0]

            if protocol == "file":
                resolved = Path(path)
                if not resolved.exists():
                    raise RefResolutionError(f"Local path does not exist: {resolved}")
                return resolved

            cache_key = self._generate_cache_key(fsspec_path)
            cache_dir = self.fsspec_cache_dir / cache_key
            original_name = self._extract_name_from_url(fsspec_path)
            final_path = cache_dir / original_name
            temp_path = cache_dir / f".tmp_{original_name}"

            if final_path.exists():
                logger.debug(f"Cache hit for {fsspec_path} → {final_path}")
                return final_path

            logger.debug(f"Cache miss for {fsspec_path}, downloading to {final_path}")
            cache_dir.mkdir(parents=True, exist_ok=True)

            try:
                if fs.isdir(path):
                    fs.get(path, str(temp_path), recursive=True)
                else:
                    fs.get_file(path, str(temp_path))

                temp_path.rename(final_path)
                logger.debug(f"Downloaded {fsspec_path} → {final_path}")
                return final_path

            except Exception:
                shutil.rmtree(temp_path, ignore_errors=True)
                raise

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
