"""Configuration models for amplifierd daemon.

These models define the structure of the daemon's configuration file,
including startup behavior, cache management, and daemon settings.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel
from pydantic import Field


class StartupConfig(BaseModel):
    """Configuration for daemon startup behavior."""

    auto_discover_profiles: bool = Field(
        default=True,
        description="Automatically discover new profiles on startup",
    )
    auto_compile_profiles: bool = Field(
        default=True,
        description="Automatically compile discovered profiles on startup",
    )
    check_cache_on_startup: bool = Field(
        default=True,
        description="Check cache freshness on startup",
    )
    update_stale_caches: bool = Field(
        default=False,
        description="Automatically update stale caches on startup (if False, only report status)",
    )
    parallel_compilation: bool = Field(
        default=True,
        description="Compile profiles in parallel when possible",
    )
    max_parallel_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Maximum number of parallel compilation workers",
    )


class DaemonConfig(BaseModel):
    """Configuration for daemon runtime behavior."""

    # Uvicorn server settings
    host: str = Field(
        default="127.0.0.1",
        description="Host to bind to (use '0.0.0.0' for LAN access)",
    )
    port: int = Field(
        default=8420,
        ge=1024,
        le=65535,
        description="Port to listen on",
    )
    workers: int = Field(
        default=1,
        ge=1,
        le=16,
        description="Number of uvicorn workers",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # CORS settings
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:5174",  # Alternative port
        ],
        description="CORS allowed origins - add your LAN hostname/IP if accessing from network (e.g., 'http://civil.lan:5173')",
    )

    # Cache and monitoring settings
    watch_for_changes: bool = Field(
        default=False,
        description="Watch for file system changes and auto-rebuild (future feature)",
    )
    watch_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Interval for checking changes when watching is enabled",
    )
    cache_ttl_hours: int | None = Field(
        default=None,
        ge=1,
        description="Cache time-to-live in hours (None = no expiration)",
    )
    enable_metrics: bool = Field(
        default=True,
        description="Enable collection of performance metrics",
    )


class Secrets(BaseModel):
    """Secrets configuration stored separately from main config.

    Stored in ~/.amplifierd/config/secrets.yaml (gitignored).
    """

    api_keys: dict[str, str] = Field(
        default_factory=dict,
        description="API keys by provider module name (e.g., 'provider-anthropic': 'sk-ant-...')",
    )

    @classmethod
    def load_from_file(cls, path: Path) -> Secrets:
        """Load secrets from YAML file.

        Args:
            path: Path to secrets file

        Returns:
            Loaded secrets (empty if file doesn't exist)
        """
        import yaml

        if not path.exists():
            return cls()

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
            return cls.model_validate(data or {})
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in secrets file: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to load secrets: {e}") from e

    def save_to_file(self, path: Path) -> None:
        """Save secrets to YAML file.

        Args:
            path: Path to save secrets file

        Raises:
            OSError: If file cannot be written
        """
        import yaml

        path.parent.mkdir(parents=True, exist_ok=True)

        # Add header comment
        header = """# Amplifierd Secrets
# This file contains sensitive credentials - DO NOT commit to version control.
# API keys are stored by provider module name.
#
# Example:
#   api_keys:
#     provider-anthropic: "sk-ant-..."
#     provider-openai: "sk-..."

"""
        with path.open("w") as f:
            f.write(header)
            yaml.safe_dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    @classmethod
    def get_default(cls) -> Secrets:
        """Get default (empty) secrets."""
        return cls()


class Config(BaseModel):
    """Complete daemon configuration."""

    startup: StartupConfig = Field(default_factory=StartupConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)

    @classmethod
    def load_from_file(cls, path: Path) -> Config:
        """Load configuration from YAML file.

        Args:
            path: Path to configuration file

        Returns:
            Loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config file is invalid
        """
        import yaml

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        try:
            with path.open() as f:
                data = yaml.safe_load(f)
            return cls.model_validate(data or {})
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to load configuration: {e}") from e

    def save_to_file(self, path: Path) -> None:
        """Save configuration to YAML file.

        Args:
            path: Path to save configuration file

        Raises:
            OSError: If file cannot be written
        """
        import yaml

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w") as f:
            yaml.safe_dump(
                self.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    @classmethod
    def get_default(cls) -> Config:
        """Get default configuration with all defaults."""
        return cls()
