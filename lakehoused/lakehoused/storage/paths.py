"""Path resolution for lakehoused storage locations.

This module provides path resolution based on LAKEHOUSED_HOME environment variable,
following XDG-like directory structure within that root.

Contract:
- Inputs: Environment variables (LAKEHOUSED_HOME)
- Outputs: Resolved Path objects
- Side Effects: Creates directories if they don't exist
"""

import os
from pathlib import Path


def get_home_dir() -> Path:
    """Get LAKEHOUSED_HOME from environment.

    Returns:
        Path to root directory (default: .lakehoused)
    """
    env_home = os.environ.get("LAKEHOUSED_HOME")
    if env_home:
        return Path(env_home).resolve()
    return Path.home() / ".lakehoused"


def get_config_dir() -> Path:
    """Get configuration directory.

    Returns:
        Path to config directory ($LAKEHOUSED_HOME/config)
    """
    config_dir: Path = get_home_dir() / "config"

    env_override: str | None = os.environ.get("LAKEHOUSED_CONFIG_DIR")
    if env_override is not None:
        config_dir = Path(env_override).resolve()

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_share_dir() -> Path:
    """Get persistent data directory.

    Returns:
        Path to share directory ($LAKEHOUSED_HOME/share)

    Environment Variables:
        LAKEHOUSED_SHARE_DIR: Override share directory location
        (falls back to $LAKEHOUSED_HOME/share if not set)

    Example:
        >>> share_dir = get_share_dir()
        >>> assert share_dir.name == "share" or "LAKEHOUSED_SHARE_DIR" in os.environ
    """
    share_dir: Path = get_home_dir() / "share"

    env_override: str | None = os.environ.get("LAKEHOUSED_SHARE_DIR")
    if env_override is not None:
        share_dir = Path(env_override).resolve()

    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def get_state_dir() -> Path:
    """Get state/cache directory.

    Returns:
        Path to state directory ($LAKEHOUSED_HOME/state)
    """
    state_dir: Path = get_home_dir() / "state"

    env_override: str | None = os.environ.get("LAKEHOUSED_STATE_DIR")
    if env_override is not None:
        state_dir = Path(env_override).resolve()

    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_log_dir() -> Path:
    """Get log directory.

    Returns:
        Path to log directory ($LAKEHOUSED_HOME/logs/lakehoused)

    Environment Variables:
        LAKEHOUSED_LOG_DIR: Override log directory location
        (falls back to $LAKEHOUSED_HOME/logs/lakehoused if not set)

    Example:
        >>> log_dir = get_log_dir()
        >>> assert log_dir.name == "lakehoused" or "LAKEHOUSED_LOG_DIR" in os.environ
    """
    log_dir: Path = get_state_dir() / "logs" / "lakehoused"

    env_override: str | None = os.environ.get("LAKEHOUSED_LOG_DIR")
    if env_override is not None:
        log_dir = Path(env_override).resolve()

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_cache_dir() -> Path:
    """Get cache directory.

    Returns:
        Path to cache directory ($LAKEHOUSED_HOME/cache/)
    """
    cache_dir: Path = get_home_dir() / "cache"

    env_override: str | None = os.environ.get("LAKEHOUSED_CACHE_DIR")
    if env_override is not None:
        cache_dir = Path(env_override).resolve()

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_git_cache_dir() -> Path:
    """Get git checkout cache directory.

    Returns:
        Path to git cache ($LAKEHOUSED_HOME/cache/git)
    """
    git_cache_dir = get_cache_dir() / "git"
    git_cache_dir.mkdir(parents=True, exist_ok=True)
    return git_cache_dir


def get_opencode_assistants_dir(configured_path: str | None = None) -> Path:
    """Get the opencode assistant store directory.

    This is the version-controlled repo containing the shared ``_library/`` and
    per-assistant ``manifests/*.json`` produced by the external amplifier2opencode
    build step.

    Args:
        configured_path: Optional path from daemon settings
            (``opencode_assistants_path``). Empty/None falls back to the default.

    Returns:
        Path to the assistant store ($LAKEHOUSED_HOME/share/opencode by default).
    """
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    assistants_dir = get_share_dir() / "opencode"
    assistants_dir.mkdir(parents=True, exist_ok=True)
    return assistants_dir
