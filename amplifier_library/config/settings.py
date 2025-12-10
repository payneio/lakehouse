"""Settings models for amplifierd daemon.

This module defines the configuration structure for the daemon itself,
separate from amplifier-core configuration.

Contract:
- Inputs: Environment variables, YAML files
- Outputs: Validated settings objects
- Side Effects: None (read-only)
"""

from pathlib import Path

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

    data_path: str = "/data"

    @field_validator('data_path')
    @classmethod
    def expand_and_resolve_path(cls, v: str) -> str:
        """Expand ~ and resolve to absolute path.

        This allows users to specify paths like:
        - "~" or "~/data" (expands to user home)
        - "./data" (resolves relative to cwd)
        - "/data" (absolute paths pass through)

        Args:
            v: Path string (may contain ~ or be relative)

        Returns:
            Absolute path as string
        """
        return str(Path(v).expanduser().resolve())

    # Collection sync behavior on startup
    force_collection_refresh_on_start: bool = False
    auto_profile_build_on_start: bool = True
    force_profile_rebuild_on_start: bool = False
