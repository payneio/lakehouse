"""Module dependency resolution service.

Resolves module sources from profiles, clones/caches using content-addressable
storage, and links modules to the correct namespace.
"""

import logging
import shutil
import subprocess
from pathlib import Path

import yaml

from amplifier_library.storage import get_share_dir
from amplifier_library.storage import get_state_dir

logger = logging.getLogger(__name__)


class ModuleResolverService:
    """Service for resolving and caching module dependencies.

    Uses content-addressable storage (git commit hashes) for deduplication
    and symlinks for namespace organization.
    """

    def __init__(self, share_dir: Path, state_dir: Path) -> None:
        """Initialize module resolver service.

        Args:
            share_dir: Root share directory containing modules/
            state_dir: State directory for content-addressable cache
        """
        self.share_dir = Path(share_dir)
        self.state_dir = Path(state_dir)
        self.modules_share_dir = self.share_dir / "modules"
        self.modules_state_dir = self.state_dir / "modules"

        self.modules_share_dir.mkdir(parents=True, exist_ok=True)
        self.modules_state_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ModuleResolverService initialized with share_dir={self.share_dir}, state_dir={self.state_dir}")

    def resolve_module_dependencies(self, profile_path: Path, collection_name: str) -> dict[str, str]:
        """Resolve all module dependencies for a profile.

        Args:
            profile_path: Path to profile YAML file
            collection_name: Collection name for module namespace

        Returns:
            Dictionary mapping module_id to status ("resolved", "cached", "error")
        """
        results: dict[str, str] = {}

        try:
            with open(profile_path) as f:
                content = f.read()

            # Extract YAML frontmatter if present
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    # Frontmatter format: --- yaml --- markdown
                    data = yaml.safe_load(parts[1])
                else:
                    # Fallback to full content
                    data = yaml.safe_load(content)
            else:
                # No frontmatter, parse as YAML
                data = yaml.safe_load(content)

            if not data or not isinstance(data, dict):
                logger.warning(f"Invalid profile YAML: {profile_path}")
                return results

            for module_type in ["providers", "tools", "hooks"]:
                modules = data.get(module_type, [])
                if not modules:
                    continue

                for module_config in modules:
                    if not isinstance(module_config, dict):
                        continue

                    module_id = module_config.get("module", "")
                    source = module_config.get("source")

                    if not source:
                        continue

                    try:
                        status = self.resolve_single_module(
                            module_id=module_id, source=source, collection_name=collection_name, module_type=module_type
                        )
                        results[module_id] = status
                    except Exception as e:
                        logger.error(f"Failed to resolve module {module_id}: {e}")
                        results[module_id] = "error"

            logger.info(f"Resolved {len(results)} modules for profile {profile_path.name}")
            return results

        except Exception as e:
            logger.error(f"Error resolving module dependencies: {e}")
            return results

    def resolve_single_module(self, module_id: str, source: str, collection_name: str, module_type: str) -> str:
        """Resolve a single module from its source.

        Args:
            module_id: Module identifier (e.g., "anthropic-provider")
            source: Git source URL (e.g., "git+https://github.com/org/repo#path")
            collection_name: Collection name for namespace
            module_type: Module type (providers, tools, hooks, orchestrators)

        Returns:
            Status string: "resolved" (newly cloned), "cached" (already exists), or "error"

        Raises:
            RuntimeError: If resolution fails
        """
        git_url, branch, subdirectory = self._parse_module_source(source)

        git_hash = self._get_content_hash(git_url, branch)
        if not git_hash:
            raise RuntimeError(f"Failed to get git hash for {git_url}")

        cache_dir = self.modules_state_dir / git_hash
        if cache_dir.exists():
            logger.debug(f"Module already cached at {cache_dir}")
            status = "cached"
        else:
            logger.info(f"Cloning module from {git_url} (hash: {git_hash})")
            self._clone_module(git_url, branch, cache_dir)
            status = "resolved"

        source_dir = cache_dir / subdirectory if subdirectory else cache_dir
        if not source_dir.exists():
            raise RuntimeError(f"Module source directory not found: {source_dir}")

        target_link = self.modules_share_dir / collection_name / module_id
        self._create_module_symlink(source_dir, target_link)

        return status

    def _parse_module_source(self, source: str) -> tuple[str, str | None, str | None]:
        """Parse module source into components.

        Args:
            source: Git source URL
                   Format: git+https://github.com/org/repo[@branch][#subdirectory]
                   Examples:
                       - git+https://github.com/org/repo
                       - git+https://github.com/org/repo@main
                       - git+https://github.com/org/repo@main#path/to/module
                       - git+https://github.com/org/repo#path/to/module

        Returns:
            Tuple of (git_url, branch, subdirectory)
        """
        git_url = source[4:] if source.startswith("git+") else source

        if "#subdirectory=" in git_url:
            git_url, subdir_part = git_url.split("#subdirectory=", 1)
            subdirectory = subdir_part
        elif "#" in git_url:
            git_url, subdirectory = git_url.split("#", 1)
        else:
            subdirectory = None

        if "@" in git_url:
            url_part, branch_part = git_url.rsplit("@", 1)
            git_url = url_part
            branch = branch_part
        else:
            branch = None

        return git_url, branch, subdirectory

    def _get_content_hash(self, git_url: str, branch: str | None) -> str | None:
        """Get git commit hash for content-addressable caching.

        Args:
            git_url: Git repository URL
            branch: Branch name or None for default

        Returns:
            Commit hash or None if failed
        """
        try:
            cmd = ["git", "ls-remote", git_url]
            if branch:
                cmd.append(f"refs/heads/{branch}")
            else:
                cmd.append("HEAD")

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            if result.stdout:
                commit_hash = result.stdout.split()[0]
                return commit_hash[:12]

            return None

        except Exception as e:
            logger.error(f"Failed to get git hash for {git_url}: {e}")
            return None

    def _clone_module(self, git_url: str, branch: str | None, cache_dir: Path) -> None:
        """Clone module repository to cache.

        Args:
            git_url: Git repository URL
            branch: Branch name or None
            cache_dir: Cache directory path

        Raises:
            RuntimeError: If git clone fails
        """
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([git_url, str(cache_dir)])

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

        logger.info(f"Successfully cloned module to {cache_dir}")

    def _create_module_symlink(self, source_dir: Path, target_link: Path) -> None:
        """Create symlink from module namespace to cache.

        Args:
            source_dir: Source directory in cache
            target_link: Target symlink path in modules namespace
        """
        target_link.parent.mkdir(parents=True, exist_ok=True)

        if target_link.exists() or target_link.is_symlink():
            if target_link.is_symlink():
                current_target = target_link.resolve()
                if current_target == source_dir:
                    logger.debug(f"Symlink already correct: {target_link}")
                    return
                target_link.unlink()
            elif target_link.is_dir():
                shutil.rmtree(target_link)
            else:
                target_link.unlink()

        target_link.symlink_to(source_dir)
        logger.info(f"Created symlink: {target_link} -> {source_dir}")


def get_module_resolver_service() -> ModuleResolverService:
    """Get module resolver service instance.

    Returns:
        ModuleResolverService instance
    """
    share_dir = get_share_dir()
    state_dir = get_state_dir()
    return ModuleResolverService(share_dir=share_dir, state_dir=state_dir)
