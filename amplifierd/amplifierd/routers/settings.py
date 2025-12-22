"""Settings router for amplifierd API.

Provides endpoints for viewing and updating daemon configuration and API keys.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import Field

from amplifierd.models.base import CamelCaseModel

from ..config.loader import get_config_path
from ..config.loader import load_config
from ..config.loader import load_secrets
from ..config.loader import save_secrets
from ..config.models import Secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# --- Response Models ---


class DaemonSettingsResponse(CamelCaseModel):
    """Daemon configuration settings."""

    host: str
    port: int
    workers: int
    log_level: str
    cors_origins: list[str]


class StartupSettingsResponse(CamelCaseModel):
    """Startup configuration settings."""

    auto_discover_profiles: bool
    auto_compile_profiles: bool
    parallel_compilation: bool
    max_parallel_workers: int


class ApiKeyInfo(CamelCaseModel):
    """API key information with masked value."""

    provider_id: str
    is_set: bool
    masked_value: str | None = None


class SettingsResponse(CamelCaseModel):
    """Complete settings response."""

    daemon: DaemonSettingsResponse
    startup: StartupSettingsResponse
    api_keys: list[ApiKeyInfo]
    config_path: str
    data_path: str  # From amplifier_library config (read-only)


class UpdateDaemonConfigRequest(CamelCaseModel):
    """Request to update daemon configuration."""

    cors_origins: list[str] | None = Field(default=None, description="CORS allowed origins")
    log_level: str | None = Field(default=None, description="Logging level")
    host: str | None = Field(default=None, description="Host to bind to")
    port: int | None = Field(default=None, description="Port to listen on")


class UpdateDaemonConfigResponse(CamelCaseModel):
    """Response after updating daemon config."""

    updated: list[str]
    message: str
    restart_required: bool


class UpdateApiKeysRequest(CamelCaseModel):
    """Request to update API keys."""

    api_keys: dict[str, str] = Field(description="API keys by provider ID (e.g., {'provider-anthropic': 'sk-ant-...'})")


class UpdateApiKeysResponse(CamelCaseModel):
    """Response after updating API keys."""

    updated: list[str]
    message: str


# --- Helper Functions ---


def _mask_api_key(key: str) -> str:
    """Mask an API key for display, showing only first and last few characters."""
    if len(key) <= 12:
        return "*" * len(key)
    return f"{key[:8]}...{key[-4:]}"


def _get_api_key_infos(secrets: Secrets) -> list[ApiKeyInfo]:
    """Get API key info list with masked values."""
    # Known providers that users might want to configure
    known_providers = [
        "provider-anthropic",
        "provider-openai",
        "provider-azure-openai",
    ]

    result = []
    seen = set()

    # Add configured keys first
    for provider_id, key in secrets.api_keys.items():
        result.append(
            ApiKeyInfo(
                provider_id=provider_id,
                is_set=True,
                masked_value=_mask_api_key(key),
            )
        )
        seen.add(provider_id)

    # Add known providers that aren't configured
    for provider_id in known_providers:
        if provider_id not in seen:
            result.append(
                ApiKeyInfo(
                    provider_id=provider_id,
                    is_set=False,
                    masked_value=None,
                )
            )

    return result


# --- Endpoints ---


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """Get current daemon settings and API key status.

    Returns daemon configuration, startup settings, and which API keys are configured.
    API key values are masked for security.
    """
    from amplifier_library.config.loader import load_config as load_library_config

    config = load_config()
    secrets = load_secrets()
    library_config = load_library_config()

    return SettingsResponse(
        daemon=DaemonSettingsResponse(
            host=config.daemon.host,
            port=config.daemon.port,
            workers=config.daemon.workers,
            log_level=config.daemon.log_level,
            cors_origins=config.daemon.cors_origins,
        ),
        startup=StartupSettingsResponse(
            auto_discover_profiles=config.startup.auto_discover_profiles,
            auto_compile_profiles=config.startup.auto_compile_profiles,
            parallel_compilation=config.startup.parallel_compilation,
            max_parallel_workers=config.startup.max_parallel_workers,
        ),
        api_keys=_get_api_key_infos(secrets),
        config_path=str(get_config_path()),
        data_path=str(library_config.data_path),
    )


@router.patch("/api-keys", response_model=UpdateApiKeysResponse)
async def update_api_keys(request: UpdateApiKeysRequest) -> UpdateApiKeysResponse:
    """Update API keys.

    Updates or adds API keys for providers. Keys are stored in secrets.yaml,
    separate from the main daemon configuration.

    To remove a key, set its value to an empty string.
    """
    if not request.api_keys:
        raise HTTPException(status_code=400, detail="No API keys provided")

    # Load current secrets
    secrets = load_secrets()
    updated = []

    for provider_id, key in request.api_keys.items():
        if key:
            # Set or update key
            secrets.api_keys[provider_id] = key
            updated.append(provider_id)
            logger.info(f"Updated API key for provider: {provider_id}")
        elif provider_id in secrets.api_keys:
            # Remove key if empty string provided
            del secrets.api_keys[provider_id]
            updated.append(provider_id)
            logger.info(f"Removed API key for provider: {provider_id}")

    # Save secrets
    save_secrets(secrets)

    return UpdateApiKeysResponse(
        updated=updated,
        message=f"Updated {len(updated)} API key(s). Changes take effect for new sessions.",
    )


@router.patch("/daemon", response_model=UpdateDaemonConfigResponse)
async def update_daemon_config(request: UpdateDaemonConfigRequest) -> UpdateDaemonConfigResponse:
    """Update daemon configuration.

    Updates daemon settings like CORS origins, logging level, host, and port.
    Changes are saved to daemon.yaml. Some changes require a daemon restart.
    """
    from ..config.loader import save_config

    # Load current config
    config = load_config()
    updated = []
    restart_required = False

    # Update fields that were provided
    if request.cors_origins is not None:
        config.daemon.cors_origins = request.cors_origins
        updated.append("cors_origins")
        restart_required = True  # CORS middleware loaded at startup

    if request.log_level is not None:
        config.daemon.log_level = request.log_level
        updated.append("log_level")

    if request.host is not None:
        config.daemon.host = request.host
        updated.append("host")
        restart_required = True

    if request.port is not None:
        config.daemon.port = request.port
        updated.append("port")
        restart_required = True

    if not updated:
        raise HTTPException(status_code=400, detail="No configuration changes provided")

    # Save config
    save_config(config)
    logger.info(f"Updated daemon config: {updated}")

    message = f"Updated {len(updated)} setting(s)."
    if restart_required:
        message += " Restart daemon for changes to take effect."

    return UpdateDaemonConfigResponse(
        updated=updated,
        message=message,
        restart_required=restart_required,
    )
