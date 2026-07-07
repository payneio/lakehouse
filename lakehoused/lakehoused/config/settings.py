"""Daemon settings model and loader.

This module defines the DaemonSettings configuration structure and provides
functions to load it from YAML files and environment variables.

Contract:
- Inputs: Environment variables, YAML files
- Outputs: Validated DaemonSettings objects
- Side Effects: Creates default config file if missing
"""

import logging
import os
from pathlib import Path
from zoneinfo import available_timezones

import yaml
from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ..storage.paths import get_config_dir

logger = logging.getLogger(__name__)


class DaemonSettings(BaseSettings):
    """Configuration for lakehoused daemon.

    This configures the daemon transport layer (HTTP/SSE), not amplifier-core.
    amplifier-core has its own configuration system.

    Attributes:
        host: Listen address (default: 127.0.0.1)
        port: Listen port (default: 8420)
        log_level: Logging level (default: info)
        workers: Number of workers (default: 1)
        data_path: Root directory for data (default: /data)

    Example:
        >>> settings = DaemonSettings()
        >>> assert settings.host == "127.0.0.1"
        >>> assert settings.port == 8420
    """

    model_config = SettingsConfigDict(
        env_prefix="LAKEHOUSED_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8420
    log_level: str = "info"
    workers: int = 1

    data_path: str = "~/amplifier"

    # opencode backend settings.
    # opencode_bin: path/name of the opencode executable (default: on PATH).
    # opencode_assistants_path: root of the version-controlled assistant repo
    #   containing _library/ and manifests/*.json (empty => $LAKEHOUSED_HOME/share/opencode).
    # opencode_max_servers: cap on concurrent pooled `opencode serve` processes.
    # opencode_server_idle_secs: idle timeout before an unused server is reaped.
    opencode_bin: str = "opencode"
    opencode_assistants_path: str = ""
    opencode_max_servers: int = 8
    opencode_server_idle_secs: int = 1800

    # Timezone for automation scheduling (IANA format, e.g., "America/Los_Angeles")
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is a valid IANA timezone identifier."""
        if v not in available_timezones():
            raise ValueError(
                f"Invalid timezone: {v}. Must be a valid IANA timezone "
                f"(e.g., 'America/Los_Angeles', 'Europe/London', 'UTC')"
            )
        return v

    @field_validator("data_path")
    @classmethod
    def expand_and_resolve_path(cls, v: str) -> str:
        """Expand ~ and resolve to absolute path, creating if needed."""
        path = Path(v).expanduser().resolve()

        # If path exists, validate it's a directory
        if path.exists():
            if not path.is_dir():
                raise ValueError(f"Data path exists but is not a directory: {path}")
            return str(path)

        # Create directory with restrictive permissions
        try:
            path.mkdir(mode=0o700, parents=False, exist_ok=True)
            logger.info(f"Created data directory: {path} (permissions: 700)")
            logger.info("Amplified directories within this path will become available projects")
        except FileNotFoundError:
            raise ValueError(f"Parent directory does not exist for data path: {path}")
        except PermissionError as e:
            raise PermissionError(f"Cannot create data directory: {path}") from e

        return str(path)


# --- Loader functions ---

DEFAULT_CONFIG = """# lakehoused daemon configuration
# This configures the daemon transport layer only

# Server settings
host: "127.0.0.1"
port: 8420
log_level: "info"
workers: 1

# Data directory root
# Default: "~/amplifier" (defined in DaemonSettings class)
# Can be overridden with LAKEHOUSED_DATA_PATH environment variable
# Supports: absolute paths (/data), ~ for home directory (~), relative paths (./data)
# data_path: "~/amplifier"

# opencode backend
# opencode_bin: opencode executable (default: found on PATH)
# opencode_assistants_path: version-controlled repo of _library/ + manifests/*.json
#   produced by amplifier2opencode (empty => $LAKEHOUSED_HOME/share/opencode)
# opencode_max_servers: cap on concurrent pooled `opencode serve` processes
# opencode_server_idle_secs: idle timeout before an unused server is reaped
# opencode_bin: "opencode"
# opencode_assistants_path: ""
# opencode_max_servers: 8
# opencode_server_idle_secs: 1800
"""


def get_config_path() -> Path:
    """Get path to config file.

    Returns:
        Path to daemon.yaml in config directory
    """
    return get_config_dir() / "daemon.yaml"


def create_default_config() -> None:
    """Create default config file if it doesn't exist."""
    config_path = get_config_path()

    if config_path.exists():
        logger.debug(f"Config file already exists: {config_path}")
        return

    config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    logger.info(f"Created default config: {config_path}")


def load_config(config_path: Path | None = None) -> DaemonSettings:
    """Load daemon configuration from YAML and environment.

    Environment variables take precedence over YAML settings.
    Variables should be prefixed with LAKEHOUSED_ (e.g., LAKEHOUSED_PORT).

    Args:
        config_path: Optional config file path (default: daemon.yaml in config dir)

    Returns:
        Validated daemon settings
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

    # Handle both flat and nested config formats:
    # Flat format (legacy): { host: ..., port: ..., data_path: ... }
    # Nested format: { daemon: { host: ..., port: ... }, data_path: ... }
    daemon_settings: dict = {}

    # First, extract from nested 'daemon:' section if present
    if "daemon" in yaml_settings and isinstance(yaml_settings["daemon"], dict):
        daemon_settings.update(yaml_settings["daemon"])

    # Then overlay root-level values (excluding nested sections)
    for key, value in yaml_settings.items():
        if key not in ("daemon", "startup") and not isinstance(value, dict):
            daemon_settings[key] = value

    # Only pass values that don't have corresponding env vars
    filtered_yaml = {}
    for key, value in daemon_settings.items():
        env_key = f"LAKEHOUSED_{key.upper()}"
        if env_key not in os.environ:
            filtered_yaml[key] = value

    # Create settings (env vars automatically loaded by Pydantic)
    settings = DaemonSettings(**filtered_yaml)

    logger.info(
        f"Daemon configuration loaded: host={settings.host}, port={settings.port}, log_level={settings.log_level}"
    )

    return settings
