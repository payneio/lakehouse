"""Response models for lakehoused API.

Pydantic models for API responses.
"""

from datetime import datetime
from typing import Any

from pydantic import Field

from lakehoused.models.base import CamelCaseModel


class MessageResponse(CamelCaseModel):
    """Response representing a message.

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        timestamp: Message timestamp
        metadata: Optional message metadata
    """

    role: str = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class TranscriptResponse(CamelCaseModel):
    """Response for session transcript.

    Attributes:
        session_id: Session ID
        messages: List of messages
    """

    session_id: str = Field(..., description="Session ID")
    messages: list[MessageResponse] = Field(..., description="List of messages")


class StatusResponse(CamelCaseModel):
    """Response for daemon status.

    Attributes:
        status: Status string (e.g., 'running')
        version: Daemon version
        uptime_seconds: Uptime in seconds
        root_dir: Root directory path
    """

    status: str = Field(..., description="Daemon status")
    version: str = Field(..., description="Daemon version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    root_dir: str = Field(..., description="Root directory path")
