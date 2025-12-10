"""Path resolution for amplifierd storage locations.

This module provides path resolution based on AMPLIFIERD_HOME environment variable,
following XDG-like directory structure within that root.

Contract:
- Inputs: Environment variables (AMPLIFIERD_HOME)
- Outputs: Resolved Path objects
- Side Effects: Creates directories if they don't exist
"""

import os
from pathlib import Path


def get_home_dir() -> Path:
    """Get AMPLIFIERD_HOME from environment.

    Returns:
        Path to root directory (default: .amplifierd)
    """
    root = os.environ.get("AMPLIFIERD_HOME", ".amplifierd")
    return Path(root).resolve()


def get_config_dir() -> Path:
    """Get configuration directory.

    Returns:
        Path to config directory ($AMPLIFIERD_HOME/config)
    """
    config_dir: Path = get_home_dir() / "config"

    env_override: str | None = os.environ.get("AMPLIFIERD_CONFIG_DIR")
    if env_override is not None:
        config_dir = Path(env_override).resolve()

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_share_dir() -> Path:
    """Get persistent data directory.

    Returns:
        Path to share directory ($AMPLIFIERD_HOME/share)

    Environment Variables:
        AMPLIFIERD_SHARE_DIR: Override share directory location
        (falls back to $AMPLIFIERD_HOME/share if not set)

    Example:
        >>> share_dir = get_share_dir()
        >>> assert share_dir.name == "share" or "AMPLIFIERD_SHARE_DIR" in os.environ
    """
    share_dir: Path = get_home_dir() / "share"

    env_override: str | None = os.environ.get("AMPLIFIERD_SHARE_DIR")
    if env_override is not None:
        share_dir = Path(env_override).resolve()

    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def get_state_dir() -> Path:
    """Get state/cache directory.

    Returns:
        Path to state directory ($AMPLIFIERD_HOME/state)
    """
    state_dir: Path = get_home_dir() / "state"

    env_override: str | None = os.environ.get("AMPLIFIERD_STATE_DIR")
    if env_override is not None:
        state_dir = Path(env_override).resolve()

    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_log_dir() -> Path:
    """Get log directory.

    Returns:
        Path to log directory ($AMPLIFIERD_HOME/logs/amplifierd)

    Environment Variables:
        AMPLIFIERD_LOG_DIR: Override log directory location
        (falls back to $AMPLIFIERD_HOME/logs/amplifierd if not set)

    Example:
        >>> log_dir = get_log_dir()
        >>> assert log_dir.name == "amplifierd" or "AMPLIFIERD_LOG_DIR" in os.environ
    """
    log_dir: Path = get_home_dir() / "logs" / "amplifierd"

    env_override: str | None = os.environ.get("AMPLIFIERD_LOG_DIR")
    if env_override is not None:
        log_dir = Path(env_override).resolve()

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_cache_dir() -> Path:
    """Get cache directory.

    Returns:
        Path to cache directory ($AMPLIFIERD_HOME/cache/)
    """
    cache_dir: Path = get_home_dir() / "cache"

    env_override: str | None = os.environ.get("AMPLIFIERD_CACHE_DIR")
    if env_override is not None:
        cache_dir = Path(env_override).resolve()

    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_git_cache_dir() -> Path:
    """Get git checkout cache directory.

    Returns:
        Path to git cache ($AMPLIFIERD_HOME/cache/git)
    """
    git_cache_dir = get_cache_dir() / "git"
    git_cache_dir.mkdir(parents=True, exist_ok=True)
    return git_cache_dir


def get_profiles_dir() -> Path:
    """Get profile manifest cache directory.

    Returns:
        Path to profile cache ($AMPLIFIERD_HOME/share/profiles)
    """
    profile_cache_dir = get_share_dir() / "profiles"
    profile_cache_dir.mkdir(parents=True, exist_ok=True)
    return profile_cache_dir


def get_compiled_profiles_dir() -> Path:
    """Get compiled profiles directory.

    Returns:
        Path to compiled profiles ($AMPLIFIERD_HOME/share/profiles)
    """
    compiled_dir = get_share_dir() / "profiles"
    compiled_dir.mkdir(parents=True, exist_ok=True)
    return compiled_dir
