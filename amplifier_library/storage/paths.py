"""Path resolution for amplifierd storage locations.

This module provides path resolution based on AMPLIFIERD_ROOT environment variable,
following XDG-like directory structure within that root.

Contract:
- Inputs: Environment variables (AMPLIFIERD_ROOT)
- Outputs: Resolved Path objects
- Side Effects: Creates directories if they don't exist
"""

import os
from pathlib import Path


def get_root_dir() -> Path:
    """Get AMPLIFIERD_ROOT from environment.

    Returns:
        Path to root directory (default: .amplifierd)

    Example:
        >>> root = get_root_dir()
        >>> assert root.is_absolute()
    """
    root = os.environ.get("AMPLIFIERD_ROOT", ".amplifierd")
    return Path(root).resolve()


def get_config_dir() -> Path:
    """Get configuration directory.

    Returns:
        Path to config directory ($AMPLIFIERD_ROOT/config)
    """
    config_dir = get_root_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_share_dir() -> Path:
    """Get persistent data directory.

    Returns:
        Path to share directory ($AMPLIFIERD_ROOT/local/share)

    """
    share_dir = get_root_dir() / "local" / "share"
    share_dir.mkdir(parents=True, exist_ok=True)
    return share_dir


def get_state_dir() -> Path:
    """Get state/cache directory.

    Returns:
        Path to state directory ($AMPLIFIERD_ROOT/local/state)

    Example:
        >>> state_dir = get_state_dir()
        >>> assert state_dir.name == "state"
    """
    state_dir = get_root_dir() / "local" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def get_log_dir() -> Path:
    """Get log directory.

    Returns:
        Path to log directory ($AMPLIFIERD_ROOT/local/logs/amplifierd)

    Example:
        >>> log_dir = get_log_dir()
        >>> assert log_dir.name == "amplifierd"
    """
    log_dir = get_root_dir() / "local" / "state" / "logs" / "amplifierd"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
