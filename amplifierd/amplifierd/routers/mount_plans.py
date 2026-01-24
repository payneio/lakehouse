"""Mount plan generation API endpoints."""

import logging

from fastapi import APIRouter
from fastapi import Body
from fastapi import HTTPException

from ..models.mount_plans import MountPlan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mount-plans", tags=["mount-plans"])


@router.post("/generate", response_model=MountPlan, status_code=201)
async def generate_mount_plan(
    bundle_name: str = Body(..., embed=True),
    project_path: str = Body(".", embed=True),
) -> MountPlan:
    """Generate mount plan from bundle.

    Creates a mount plan by loading a bundle and generating configuration.
    The mount plan contains all agents, context, and modules organized and
    ready for session initialization.

    Args:
        bundle_name: Bundle identifier (e.g., "foundation/base")
        project_path: Path to project directory for working_dir context

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
            "bundle_name": "foundation/base",
            "project_path": "/path/to/project"
        }
        ```
    """
    try:
        import uuid

        from lakehouse_library.bundles import LakehouseBundleManager

        from ..config.loader import load_secrets

        bundle_manager = LakehouseBundleManager()

        # Generate a temporary session ID for mount plan generation
        session_id = f"preview_{uuid.uuid4().hex[:8]}"

        # Load secrets for API key injection
        secrets = load_secrets()
        api_key = next(iter(secrets.api_keys.values()), None) if secrets.api_keys else None

        mount_plan = await bundle_manager.generate_mount_plan(
            bundle_ref=bundle_name,
            session_id=session_id,
            project_path=project_path,
            api_key=api_key,
        )

        return mount_plan  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to generate mount plan: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate mount plan: {str(exc)}") from exc
