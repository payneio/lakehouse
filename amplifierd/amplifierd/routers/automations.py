"""Automation API endpoints for scheduled workflows.

Manages automation lifecycle:
- Create/update/delete automations
- Enable/disable scheduling
- Query execution history
- List and filter automations by project
"""

import logging
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Literal

from fastapi import APIRouter
from fastapi import Body
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from pydantic import BaseModel
from pydantic import Field as PydanticField

from amplifier_library.automations.manager import AutomationManager
from amplifier_library.models.automations import Automation
from amplifier_library.models.automations import ExecutionRecord
from amplifier_library.models.automations import ScheduleConfig
from amplifier_library.storage import get_state_dir

if TYPE_CHECKING:
    from amplifierd.services.automation_scheduler import AutomationScheduler  # noqa: F401

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id:path}/automations", tags=["automations"])


def get_automation_manager() -> AutomationManager:
    """Get automation manager instance.

    Returns:
        AutomationManager configured with state directory
    """
    state_dir = get_state_dir()
    return AutomationManager(storage_dir=state_dir)


def get_automation_scheduler(request: Request) -> "AutomationScheduler | None":
    """Get automation scheduler from app state.

    Args:
        request: FastAPI request object

    Returns:
        AutomationScheduler instance from app state, or None if not available
    """
    return getattr(request.app.state, "automation_scheduler", None)


# --- Request/Response Models ---


class AutomationCreate(BaseModel):
    """Request model for creating an automation."""

    name: str = PydanticField(..., max_length=200, description="Human-readable automation name")
    message: str = PydanticField(..., description="Message to send to agent on execution")
    schedule: ScheduleConfig = PydanticField(..., description="Schedule configuration")
    enabled: bool = PydanticField(default=True, description="Whether automation is active")


class AutomationUpdate(BaseModel):
    """Request model for updating an automation."""

    name: str | None = PydanticField(None, max_length=200, description="Human-readable automation name")
    message: str | None = PydanticField(None, description="Message to send to agent on execution")
    schedule: ScheduleConfig | None = PydanticField(None, description="Schedule configuration")
    enabled: bool | None = PydanticField(None, description="Whether automation is active")


class AutomationResponse(BaseModel):
    """Response model for automation data."""

    automation: Automation = PydanticField(..., description="Complete automation data")


class AutomationList(BaseModel):
    """Response model for list of automations."""

    automations: list[Automation] = PydanticField(..., description="List of automations")
    total: int = PydanticField(..., description="Total count of automations matching filters")


class ExecutionHistory(BaseModel):
    """Response model for execution history."""

    executions: list[ExecutionRecord] = PydanticField(..., description="Execution records")
    total: int = PydanticField(..., description="Total count of executions")


# --- Lifecycle Endpoints ---


@router.post("/", status_code=201, response_model=AutomationResponse)
async def create_automation(
    project_id: str,
    automation: AutomationCreate,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    scheduler: Annotated["AutomationScheduler | None", Depends(get_automation_scheduler)] = None,
) -> AutomationResponse:
    """Create new automation for project.

    Creates automation and registers it with the scheduler if enabled.

    Args:
        project_id: Path to amplified directory
        automation: Automation configuration
        manager: Automation manager dependency

    Returns:
        Created automation

    Raises:
        HTTPException:
            - 400 if validation fails or duplicate name
            - 404 if project not found
            - 500 for other errors

    Example:
        ```json
        {
            "name": "Daily Standup Report",
            "message": "Generate standup report from recent commits",
            "schedule": {
                "type": "cron",
                "value": "0 9 * * *"
            },
            "enabled": true
        }
        ```
    """
    try:
        # Create automation
        # Note: We don't validate project existence here because:
        # 1. Automations can be created before directories are fully set up
        # 2. Validation happens naturally during execution when creating sessions
        # 3. This keeps the API simple and flexible
        created = manager.create_automation(
            project_id=project_id,
            name=automation.name,
            message=automation.message,
            schedule=automation.schedule,
            enabled=automation.enabled,
        )

        # Register with scheduler if enabled and scheduler is available
        if created.enabled and scheduler is not None:
            try:
                await scheduler.schedule_automation(created)
                logger.info(f"Automation {created.id} scheduled successfully")
            except Exception as e:
                logger.error(f"Failed to schedule automation {created.id}: {e}")
                # Don't fail the creation, automation is still persisted

        logger.info(f"Created automation {created.id} ('{created.name}') for project {project_id}")
        return AutomationResponse(automation=created)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Failed to create automation: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/", response_model=AutomationList)
async def list_automations(
    project_id: str,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    enabled: bool | None = Query(None, description="Filter by enabled status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> AutomationList:
    """List automations for project with optional filters.

    Args:
        project_id: Path to amplified directory
        enabled: Optional filter by enabled status
        limit: Maximum results (1-100, default 50)
        offset: Results to skip (default 0)
        manager: Automation manager dependency

    Returns:
        Filtered list of automations

    Raises:
        HTTPException:
            - 500 for errors

    Example:
        ```
        GET /api/v1/projects/my-project/automations?enabled=true&limit=10
        ```
    """
    try:
        # Get all matching automations
        all_automations = manager.list_automations(project_id=project_id, enabled=enabled)

        # Apply pagination
        total = len(all_automations)
        automations = all_automations[offset : offset + limit]

        return AutomationList(automations=automations, total=total)

    except Exception as exc:
        logger.error(f"Failed to list automations: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    project_id: str,
    automation_id: str,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
) -> AutomationResponse:
    """Get automation by ID.

    Args:
        project_id: Path to amplified directory
        automation_id: Automation identifier
        manager: Automation manager dependency

    Returns:
        Automation data

    Raises:
        HTTPException:
            - 404 if automation not found or doesn't belong to project
            - 500 for other errors
    """
    try:
        automation = manager.get_automation(automation_id)

        if automation is None:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        # Verify automation belongs to this project
        if automation.project_id != project_id:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found in project {project_id}")

        return AutomationResponse(automation=automation)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get automation {automation_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.patch("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    project_id: str,
    automation_id: str,
    update: AutomationUpdate,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    scheduler: Annotated["AutomationScheduler | None", Depends(get_automation_scheduler)] = None,
) -> AutomationResponse:
    """Update automation fields.

    Updates one or more automation fields. Reschedules automation if schedule changes.

    Args:
        project_id: Path to amplified directory
        automation_id: Automation identifier
        update: Fields to update
        manager: Automation manager dependency

    Returns:
        Updated automation

    Raises:
        HTTPException:
            - 400 if validation fails or duplicate name
            - 404 if automation not found or doesn't belong to project
            - 500 for other errors

    Example:
        ```json
        {
            "enabled": false,
            "schedule": {
                "type": "interval",
                "value": "2h"
            }
        }
        ```
    """
    try:
        # Check automation exists and belongs to project
        existing = manager.get_automation(automation_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        if existing.project_id != project_id:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found in project {project_id}")

        # Build update dict with only provided fields
        updates = {}
        if update.name is not None:
            updates["name"] = update.name
        if update.message is not None:
            updates["message"] = update.message
        if update.schedule is not None:
            updates["schedule"] = update.schedule
        if update.enabled is not None:
            updates["enabled"] = update.enabled

        if not updates:
            # No changes requested, return existing
            return AutomationResponse(automation=existing)

        # Update automation
        updated = manager.update_automation(automation_id, **updates)

        # Update scheduler registration if schedule or enabled changed
        if scheduler is not None and ("schedule" in updates or "enabled" in updates):
            try:
                if updated.enabled:
                    await scheduler.schedule_automation(updated)
                    logger.info(f"Automation {automation_id} rescheduled successfully")
                else:
                    await scheduler.unschedule_automation(automation_id)
                    logger.info(f"Automation {automation_id} unscheduled successfully")
            except Exception as e:
                logger.error(f"Failed to update scheduler for automation {automation_id}: {e}")
                # Don't fail the update, automation is still persisted

        logger.info(f"Updated automation {automation_id}")
        return AutomationResponse(automation=updated)

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to update automation {automation_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    project_id: str,
    automation_id: str,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    scheduler: Annotated["AutomationScheduler | None", Depends(get_automation_scheduler)] = None,
) -> None:
    """Delete automation and its execution history.

    Permanently removes automation and all associated data. Cannot be undone.

    Args:
        project_id: Path to amplified directory
        automation_id: Automation identifier
        manager: Automation manager dependency

    Raises:
        HTTPException:
            - 404 if automation not found or doesn't belong to project
            - 500 for other errors
    """
    try:
        # Check automation exists and belongs to project
        existing = manager.get_automation(automation_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        if existing.project_id != project_id:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found in project {project_id}")

        # Unregister from scheduler first
        if scheduler is not None:
            try:
                await scheduler.unschedule_automation(automation_id)
                logger.info(f"Automation {automation_id} unscheduled before deletion")
            except Exception as e:
                logger.error(f"Failed to unschedule automation {automation_id}: {e}")
                # Continue with deletion anyway

        # Delete automation
        if not manager.delete_automation(automation_id):
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        logger.info(f"Deleted automation {automation_id}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to delete automation {automation_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.patch("/{automation_id}/toggle", response_model=dict)
async def toggle_automation(
    project_id: str,
    automation_id: str,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    scheduler: Annotated["AutomationScheduler | None", Depends(get_automation_scheduler)] = None,
    enabled: bool = Body(..., embed=True),
) -> dict:
    """Enable or disable automation.

    Convenience endpoint for toggling automation on/off without full update.

    Args:
        project_id: Path to amplified directory
        automation_id: Automation identifier
        enabled: New enabled status
        manager: Automation manager dependency

    Returns:
        Updated enabled status

    Raises:
        HTTPException:
            - 404 if automation not found or doesn't belong to project
            - 500 for other errors

    Example:
        ```json
        {
            "enabled": true
        }
        ```

        Response:
        ```json
        {
            "automation_id": "abc-123",
            "enabled": true
        }
        ```
    """
    try:
        # Check automation exists and belongs to project
        existing = manager.get_automation(automation_id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        if existing.project_id != project_id:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found in project {project_id}")

        # Update enabled status
        updated = manager.update_automation(automation_id, enabled=enabled)

        # Update scheduler registration
        if scheduler is not None:
            try:
                if enabled:
                    await scheduler.schedule_automation(updated)
                    logger.info(f"Automation {automation_id} scheduled after toggle")
                else:
                    await scheduler.unschedule_automation(automation_id)
                    logger.info(f"Automation {automation_id} unscheduled after toggle")
            except Exception as e:
                logger.error(f"Failed to update scheduler for automation {automation_id}: {e}")
                # Don't fail the toggle, automation is still persisted

        logger.info(f"Toggled automation {automation_id} enabled={enabled}")
        return {"automation_id": automation_id, "enabled": updated.enabled}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to toggle automation {automation_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


@router.get("/{automation_id}/executions", response_model=ExecutionHistory)
async def get_execution_history(
    project_id: str,
    automation_id: str,
    manager: Annotated[AutomationManager, Depends(get_automation_manager)],
    status: Literal["success", "failed"] | None = Query(None, description="Filter by execution status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> ExecutionHistory:
    """Get execution history for automation.

    Returns historical execution records sorted by execution time (newest first).
    Each execution creates a session that can be inspected via session endpoints.

    Args:
        project_id: Path to amplified directory
        automation_id: Automation identifier
        status: Optional filter by execution status
        limit: Maximum results (1-100, default 50)
        offset: Results to skip (default 0)
        manager: Automation manager dependency

    Returns:
        Execution history records

    Raises:
        HTTPException:
            - 404 if automation not found or doesn't belong to project
            - 500 for other errors

    Example:
        ```
        GET /api/v1/projects/my-project/automations/abc-123/executions?status=success&limit=10
        ```
    """
    try:
        # Check automation exists and belongs to project
        automation = manager.get_automation(automation_id)
        if automation is None:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found")

        if automation.project_id != project_id:
            raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found in project {project_id}")

        # Get execution history
        executions = manager.get_execution_history(
            automation_id=automation_id,
            status=status,
            limit=limit,
            offset=offset,
        )

        # Get total count (without pagination)
        all_executions = manager.get_execution_history(automation_id=automation_id, status=status, limit=10000)
        total = len(all_executions)

        return ExecutionHistory(executions=executions, total=total)

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to get execution history for {automation_id}: {exc}")
        raise HTTPException(status_code=500, detail="Internal server error") from exc
