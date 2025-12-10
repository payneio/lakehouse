"""Configuration loading for amplifierd daemon.

This module handles loading daemon configuration from YAML files
and environment variables.

Contract:
- Inputs: Config file paths, environment variables
- Outputs: DaemonSettings objects
- Side Effects: Creates default config file if missing
"""

import logging
from pathlib import Path

import yaml

from ..storage.paths import get_config_dir
from .settings import DaemonSettings

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = """# amplifierd daemon configuration
# This configures the daemon transport layer only
# For amplifier-core configuration, see amplifier-core docs

# Server settings
host: "127.0.0.1"
port: 8420
log_level: "info"
workers: 1

# Data directory root
# Default: "/data" (defined in DaemonSettings class)
# Can be overridden with AMPLIFIERD_DATA_PATH environment variable
# Supports: absolute paths (/data), ~ for home directory (~), relative paths (./data)
# data_path: "/data"
"""


def get_config_path() -> Path:
    """Get path to config file.

    Returns:
        Path to daemon.yaml in config directory

    Example:
        >>> config_path = get_config_path()
        >>> assert config_path.name == "daemon.yaml"
    """
    return get_config_dir() / "daemon.yaml"


def create_default_config() -> None:
    """Create default config file if it doesn't exist.

    Example:
        >>> create_default_config()
        >>> assert get_config_path().exists()
    """
    config_path = get_config_path()

    if config_path.exists():
        logger.debug(f"Config file already exists: {config_path}")
        return

    config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    logger.info(f"Created default config: {config_path}")


def load_config(config_path: Path | None = None) -> DaemonSettings:
    """Load daemon configuration from YAML and environment.

    Environment variables take precedence over YAML settings.
    Variables should be prefixed with AMPLIFIERD_ (e.g., AMPLIFIERD_PORT).

    Args:
        config_path: Optional config file path (default: daemon.yaml in config dir)

    Returns:
        Validated daemon settings

    Example:
        >>> settings = load_config()
        >>> assert isinstance(settings, DaemonSettings)
        >>> assert settings.port > 0
    """
    if config_path is None:
        config_path = get_config_path()

    # Create default config if it doesn't exist
    if not config_path.exists():
        create_default_config()

    # Load YAML config
    yaml_settings = {}
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                yaml_settings = yaml.safe_load(f) or {}
            logger.debug(f"Loaded config from {config_path}")
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default settings and environment variables")

    # Create settings object with YAML as defaults
    # Environment variables will override YAML due to Pydantic's _env_file setting
    # We use model_validate to ensure proper precedence: defaults < YAML < env vars
    import os

    # Only pass YAML values that don't have corresponding env vars
    filtered_yaml = {}
    for key, value in yaml_settings.items():
        env_key = f"AMPLIFIERD_{key.upper()}"
        if env_key not in os.environ:
            filtered_yaml[key] = value

    # Create settings (env vars automatically loaded by Pydantic)
    settings = DaemonSettings(**filtered_yaml)

    logger.info(
        f"Daemon configuration loaded: host={settings.host}, port={settings.port}, log_level={settings.log_level}"
    )

    return settings
