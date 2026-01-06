"""Mount plan generation API endpoints."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from amplifier_library.config.loader import load_config
from amplifier_library.storage import get_cache_dir

from ..models.mount_plans import MountPlan
from ..models.mount_plans import MountPlanRequest
from ..services.bundle_service import BundleService

router = APIRouter(prefix="/api/v1/mount-plans", tags=["mount-plans"])


def get_bundle_service() -> BundleService:
    """Get bundle service instance.

    Returns:
        BundleService instance
    """
    config = load_config()
    bundles_dir = Path(config.data_path) / "bundles"
    cache_dir = get_cache_dir()
    return BundleService(bundles_dir=bundles_dir, home_dir=cache_dir)


@router.post("/generate", response_model=MountPlan, status_code=201)
async def generate_mount_plan(
    request: MountPlanRequest,
    service: Annotated[BundleService, Depends(get_bundle_service)],
) -> MountPlan:
    """Generate mount plan from bundle.

    Creates a mount plan by loading and preparing a bundle.
    The mount plan contains all agents, context, and modules organized and
    ready for session initialization.

    Args:
        request: Mount plan request with profile_id and optional settings
        service: Bundle service instance

    Returns:
        Complete mount plan with all resources mounted

    Raises:
        HTTPException:
            - 404 if bundle not found
            - 400 if request is invalid
            - 500 for other errors

    Example:
        ```json
        {
            "profile_id": "foundation/base",
            "session_id": "my-session-123",
            "settings_overrides": {
                "llm": {"model": "gpt-4"}
            }
        }
        ```
    """
    try:
        prepared = await service.load_bundle(request.profile_id)
        mount_plan_dict = service.get_mount_plan(prepared)
        # Return the dict directly since we're using dict-based plans
        return mount_plan_dict  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate mount plan: {str(exc)}") from exc
