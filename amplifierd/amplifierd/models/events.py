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

    event_type: Literal["session:created"] = "session:created"
    session_id: str
    session_name: str | None
    project_id: str  # Required for sessions
    is_unread: bool
    created_by: Literal["user", "automation"]


class SessionUpdatedEvent(GlobalEvent):
    """Emitted when session metadata changes."""

    event_type: Literal["session:updated"] = "session:updated"
    session_id: str
    project_id: str
    fields_changed: list[str]


class AutomationTriggeredEvent(GlobalEvent):
    """Emitted when automation executes."""

    event_type: Literal["automation:triggered"] = "automation:triggered"
    automation_id: str
    automation_name: str
    project_id: str
