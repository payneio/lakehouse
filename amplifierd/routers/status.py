"""Status router for amplifierd API.

Provides health check and status information.
"""

import logging
import time

from fastapi import APIRouter

from amplifier_library.config.loader import load_config

from ..models import StatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["status"])

# Track daemon start time for uptime calculation
_start_time = time.time()


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get daemon status.

    Returns:
        Daemon status information including version, uptime, and root directory
    """
    uptime = time.time() - _start_time
    config = load_config()
    root_dir = str(config.data_path)

    return StatusResponse(
        status="running",
        version="0.1.0",
        uptime_seconds=uptime,
        root_dir=root_dir,
    )


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Simple health status
    """
    return {"status": "healthy"}
