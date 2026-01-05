"""Settings models for amplifierd daemon.

This module defines the configuration structure for the daemon itself,
separate from amplifier-core configuration.

Contract:
- Inputs: Environment variables, YAML files
- Outputs: Validated settings objects
- Side Effects: None (read-only)
"""

from pathlib import Path
from zoneinfo import available_timezones

from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class DaemonSettings(BaseSettings):
    """Configuration for amplifierd daemon.

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
        env_prefix="AMPLIFIERD_",
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

    # Timezone for automation scheduling (IANA format, e.g., "America/Los_Angeles")
    timezone: str = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone is a valid IANA timezone identifier.

        Args:
            v: Timezone string (e.g., "America/Los_Angeles", "UTC", "Europe/London")

        Returns:
            Validated timezone string

        Raises:
            ValueError: If timezone is not a valid IANA identifier
        """
        if v not in available_timezones():
            raise ValueError(
                f"Invalid timezone: {v}. Must be a valid IANA timezone "
                f"(e.g., 'America/Los_Angeles', 'Europe/London', 'UTC')"
            )
        return v

    @field_validator('data_path')
    @classmethod
    def expand_and_resolve_path(cls, v: str) -> str:
        """Expand ~ and resolve to absolute path, creating if needed.

        This allows users to specify paths like:
        - "~" or "~/amplifier" (expands to user home)
        - "./data" (resolves relative to cwd)
        - "/data" (absolute paths pass through)

        The directory will be created with restrictive permissions (700)
        if it doesn't exist.

        Args:
            v: Path string (may contain ~ or be relative)

        Returns:
            Absolute path as string

        Raises:
            ValueError: If path exists but is not a directory
            PermissionError: If directory cannot be created
        """
        import logging
        from pathlib import Path

        logger = logging.getLogger(__name__)
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
            logger.info(f"Amplified directories within this path will become available projects")
        except FileNotFoundError:
            # Parent directory doesn't exist - don't create it
            raise ValueError(f"Parent directory does not exist for data path: {path}")
        except PermissionError as e:
            raise PermissionError(f"Cannot create data directory: {path}") from e

        return str(path)

    # Profile compilation behavior on startup
    auto_profile_build_on_start: bool = True
    force_profile_rebuild_on_start: bool = False
