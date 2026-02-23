"""Projects API endpoints."""

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from lakehoused.config.settings import load_config
from lakehoused.models.projects import AgentsContentResponse
from lakehoused.models.projects import AgentsContentUpdate
from lakehoused.models.projects import Project
from lakehoused.models.projects import ProjectCreate
from lakehoused.models.projects import ProjectList
from lakehoused.models.projects import ProjectUpdate
from lakehoused.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@lru_cache(maxsize=1)
def get_service() -> ProjectService:
    """Get project service singleton instance."""
    config = load_config()
    data_path = Path(config.data_path)
    return ProjectService(data_path)


@router.post("/", response_model=Project, status_code=201)
async def create_project(
    create_req: ProjectCreate,
    service: ProjectService = Depends(get_service),
) -> Project:
    """Create/register a new project.

    Creates directory structure and .amplified marker if requested.
    Resolves default_bundle using inheritance if not provided.

    Args:
        create_req: Creation request with path, optional profile, metadata
        service: Injected service instance

    Returns:
        Created Project with resolved profile

    Raises:
        400: Invalid path (absolute, contains '..', escapes root)
        400: Directory is already a project
        500: Filesystem error
    """
    try:
        return service.create(create_req)
    except ValueError as e:
        logger.warning(f"Invalid create request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/root", response_model=Project)
async def get_root_project(
    service: ProjectService = Depends(get_service),
) -> Project:
    """Get root project (special endpoint for path '.').

    FastAPI routes /projects/. to the list endpoint,
    so we provide /projects/root as an explicit route.

    Returns:
        Root project with metadata and agents_content

    Raises:
        404: Root directory is not a project
    """
    try:
        project = service.get(".")

        if not project:
            raise HTTPException(status_code=404, detail="Root directory is not a project")

        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get root project: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/", response_model=ProjectList)
async def list_projects(
    service: ProjectService = Depends(get_service),
) -> ProjectList:
    """List all projects within LAKEHOUSED_DATA_PATH.

    Discovers projects by walking filesystem to find .amplified markers.

    Returns:
        List of all projects with metadata
    """
    try:
        projects = service.list_all()
        return ProjectList(
            projects=projects,
            total=len(projects),
        )
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/{relative_path:path}", response_model=Project)
async def get_project(
    relative_path: str,
    service: ProjectService = Depends(get_service),
) -> Project:
    """Get specific project by relative path.

    Args:
        relative_path: Path relative to LAKEHOUSED_DATA_PATH
        service: Injected service instance

    Returns:
        Project with metadata

    Raises:
        404: Directory not found or not a project
    """
    try:
        project = service.get(relative_path)

        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {relative_path}")

        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.patch("/{relative_path:path}", response_model=Project)
async def update_project(
    relative_path: str,
    update_req: ProjectUpdate,
    service: ProjectService = Depends(get_service),
) -> Project:
    """Update project metadata.

    Merges provided metadata with existing metadata.

    Args:
        relative_path: Path relative to LAKEHOUSED_DATA_PATH
        update_req: Update request with metadata changes
        service: Injected service instance

    Returns:
        Updated Project

    Raises:
        404: Directory not found or not a project
        500: Update failed
    """
    try:
        project = service.update(relative_path, update_req)

        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {relative_path}")

        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.put("/root/agents", response_model=AgentsContentResponse)
async def update_root_agents_content(
    update_req: AgentsContentUpdate,
    service: ProjectService = Depends(get_service),
) -> AgentsContentResponse:
    """Update AGENTS.md file for root project (special endpoint for path '.').

    FastAPI has issues routing '.' in paths, so we provide /root/agents as an explicit route.

    Args:
        update_req: New content for AGENTS.md
        service: Injected service instance

    Returns:
        Success status and message

    Raises:
        404: Root directory is not a project
        400: Invalid content (empty)
        500: File write failed
    """
    try:
        # Basic validation
        if not update_req.content.strip():
            raise HTTPException(status_code=400, detail="AGENTS.md content cannot be empty")

        # Update agents file for root directory
        success = service.update_agents_content(".", update_req.content)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Root directory is not a project",
            )

        return AgentsContentResponse(
            success=True,
            message="AGENTS.md updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update AGENTS.md for root project: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update AGENTS.md: {str(e)}",
        ) from e


@router.put("/{relative_path:path}/agents", response_model=AgentsContentResponse)
async def update_agents_content(
    relative_path: str,
    update_req: AgentsContentUpdate,
    service: ProjectService = Depends(get_service),
) -> AgentsContentResponse:
    """Update AGENTS.md file for a project.

    Args:
        relative_path: Path relative to LAKEHOUSED_DATA_PATH
        update_req: New content for AGENTS.md
        service: Injected service instance

    Returns:
        Success status and message

    Raises:
        404: Directory not found or not a project
        400: Invalid content (empty)
        500: File write failed
    """
    try:
        # Basic validation
        if not update_req.content.strip():
            raise HTTPException(status_code=400, detail="AGENTS.md content cannot be empty")

        # Update agents file
        success = service.update_agents_content(relative_path, update_req.content)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Project not found: {relative_path}",
            )

        return AgentsContentResponse(
            success=True,
            message="AGENTS.md updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update AGENTS.md for {relative_path}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update AGENTS.md: {str(e)}",
        ) from e


@router.delete("/{relative_path:path}", status_code=204)
async def delete_project(
    relative_path: str,
    remove_marker: bool = False,
    service: ProjectService = Depends(get_service),
) -> None:
    """Unregister/delete project.

    Args:
        relative_path: Path relative to LAKEHOUSED_DATA_PATH
        remove_marker: If True, also delete .amplified directory from filesystem
        service: Injected service instance

    Raises:
        404: Directory not found or not a project
        409: Cannot delete - project has active sessions
        500: Deletion failed

    Note: Deletion protection (409) will be implemented when session
    integration is complete. For now, deletion always proceeds if directory exists.
    """
    try:
        # Session deletion protection will be implemented when session integration is complete
        # The service will check for active sessions and raise 409 if any exist

        success = service.delete(relative_path, remove_marker=remove_marker)

        if not success:
            raise HTTPException(status_code=404, detail=f"Project not found: {relative_path}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {relative_path}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
