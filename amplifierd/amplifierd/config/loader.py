"""Configuration loader for amplifierd daemon.

Handles loading configuration from files, environment variables, and defaults.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from amplifier_library.storage.paths import get_config_dir

from .models import Config

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Get the default configuration file path.

    Returns:
        Path to configuration file (may not exist yet)
    """
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "daemon.yaml"


def load_config(config_path: Path | None = None) -> Config:
    """Load daemon configuration.

    Loads configuration with the following precedence (highest to lowest):
    1. Environment variables (AMPLIFIERD_*)
    2. Configuration file (if exists)
    3. Default values

    Args:
        config_path: Optional path to configuration file. If None, uses default location.

    Returns:
        Loaded configuration

    Raises:
        ValueError: If configuration file is invalid
    """
    # Use default path if not provided
    if config_path is None:
        config_path = get_config_path()

    # Start with defaults
    if config_path.exists():
        logger.info(f"Loading configuration from {config_path}")
        try:
            config = Config.load_from_file(config_path)
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            logger.info("Using default configuration")
            config = Config.get_default()
    else:
        logger.info(f"No configuration file found at {config_path}, using defaults")
        config = Config.get_default()

    # Apply environment variable overrides
    config = _apply_env_overrides(config)

    return config


def _apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides to configuration.

    Environment variables follow the pattern: AMPLIFIERD_SECTION_KEY
    Examples:
        AMPLIFIERD_STARTUP_AUTO_DISCOVER_PROFILES=false
        AMPLIFIERD_DAEMON_LOG_LEVEL=DEBUG

    Args:
        config: Configuration to override

    Returns:
        Configuration with environment overrides applied
    """
    # Convert config to dict for manipulation
    config_dict = config.model_dump()

    # Check for startup overrides
    startup_overrides = {}
    for key in [
        "auto_discover_profiles",
        "auto_compile_profiles",
        "check_cache_on_startup",
        "update_stale_caches",
        "parallel_compilation",
        "max_parallel_workers",
    ]:
        env_var = f"AMPLIFIERD_STARTUP_{key.upper()}"
        if env_var in os.environ:
            value = os.environ[env_var]
            # Parse value based on type
            if key == "max_parallel_workers":
                startup_overrides[key] = int(value)
            else:
                startup_overrides[key] = value.lower() in ("true", "1", "yes")
            logger.info(f"Environment override: startup.{key} = {startup_overrides[key]}")

    if startup_overrides:
        config_dict["startup"].update(startup_overrides)

    # Check for daemon overrides
    daemon_overrides = {}
    for key in [
        "host",
        "port",
        "workers",
        "log_level",
        "cors_origins",
        "watch_for_changes",
        "watch_interval_seconds",
        "cache_ttl_hours",
        "enable_metrics",
    ]:
        env_var = f"AMPLIFIERD_DAEMON_{key.upper()}"
        if env_var in os.environ:
            value = os.environ[env_var]
            # Parse value based on type
            if key == "port" or key == "workers" or key == "watch_interval_seconds":
                daemon_overrides[key] = int(value)
            elif key == "cache_ttl_hours":
                daemon_overrides[key] = int(value) if value.lower() != "none" else None
            elif key in ("host", "log_level"):
                daemon_overrides[key] = value
            elif key == "cors_origins":
                # Parse comma-separated list
                daemon_overrides[key] = [origin.strip() for origin in value.split(",")]
            else:
                daemon_overrides[key] = value.lower() in ("true", "1", "yes")
            logger.info(f"Environment override: daemon.{key} = {daemon_overrides[key]}")

    if daemon_overrides:
        config_dict["daemon"].update(daemon_overrides)

    # Rebuild config from dict
    return Config.model_validate(config_dict)


def save_example_config(path: Path | None = None) -> Path:
    """Save an example configuration file with all defaults documented.

    Args:
        path: Optional path to save to. If None, uses default location with .example suffix.

    Returns:
        Path where example config was saved

    Raises:
        OSError: If file cannot be written
    """
    if path is None:
        path = get_config_path().with_suffix(".example.yaml")

    # Create default config
    config = Config.get_default()

    # Add comments by prepending to the YAML
    config.save_to_file(path)

    # Read back and add header comment
    content = path.read_text()
    header = """# Amplifierd Daemon Configuration
#
# This is an example configuration file showing all available options with their defaults.
# Copy this to daemon.yaml and customize as needed.
#
# Configuration precedence (highest to lowest):
# 1. Environment variables (AMPLIFIERD_SECTION_KEY)
# 2. This configuration file
# 3. Built-in defaults

"""
    path.write_text(header + content)

    logger.info(f"Saved example configuration to {path}")
    return path
