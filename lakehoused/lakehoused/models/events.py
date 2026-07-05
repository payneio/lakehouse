"""Global event models for SSE streaming.

These events are emitted by the system and can be subscribed to via the global
SSE endpoint at /api/v1/events.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field


class GlobalEvent(BaseModel):
    """Base model for global SSE events."""

    event_type: str
    timestamp: datetime = Field(default_factory=datetime.now)
    project_id: str | None = Field(None, description="Project filter (None = daemon-wide)")


class SessionCreatedEvent(GlobalEvent):
    """Emitted when new session is created."""

    event_type: Literal["session:created"] = "session:created"  # type: ignore[assignment]
    session_id: str
    session_name: str | None = None
    is_unread: bool = False
    created_by: Literal["user", "automation"] = "user"


class SessionUpdatedEvent(GlobalEvent):
    """Emitted when session metadata changes."""

    event_type: Literal["session:updated"] = "session:updated"  # type: ignore[assignment]
    session_id: str
    fields_changed: list[str] = Field(default_factory=list)


class AutomationTriggeredEvent(GlobalEvent):
    """Emitted when automation executes."""

    event_type: Literal["automation:triggered"] = "automation:triggered"  # type: ignore[assignment]
    automation_id: str
    automation_name: str
