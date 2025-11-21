"""Request models for amplifierd API.

Pydantic models for validating incoming API requests.
"""

from typing import Any

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class CreateSessionRequest(CamelCaseModel):
    """Request to create a new session.

    Attributes:
        profile: Profile name for this session
        context: Optional session-specific context data
    """

    profile: str = Field(..., description="Profile name for this session")
    context: dict[str, Any] | None = Field(default=None, description="Optional session-specific context data")


class SendMessageRequest(CamelCaseModel):
    """Request to send a message to a session.

    Attributes:
        content: Message content/prompt
        stream: Whether to stream the response (for execute endpoint)
    """

    content: str = Field(..., description="Message content or user prompt")
    stream: bool = Field(default=False, description="Whether to stream the response")


class UpdateContextRequest(CamelCaseModel):
    """Request to update session context.

    Attributes:
        context: Context updates to merge into session
    """

    context: dict[str, Any] = Field(..., description="Context updates to merge")
