"""Bundle management API endpoints."""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["bundles"])


@router.get("/")
async def list_bundles() -> list[dict[str, str]]:
    """List all available bundles.

    Returns list of bundles with their names. Bundles are loaded from
    ~/.amplifierd/bundles/ directory.

    Returns:
        List of bundle info objects with name field.

    Example response:
        [
            {"name": "software-developer"},
            {"name": "research-assistant"},
            {"name": "writing-helper"}
        ]
    """
    from amplifier_library.bundles import LakehouseBundleManager

    bundle_manager = LakehouseBundleManager()
    bundle_names = bundle_manager.list_available_bundles()

    # Return as list of objects for consistency with other APIs
    return [{"name": name} for name in bundle_names]
