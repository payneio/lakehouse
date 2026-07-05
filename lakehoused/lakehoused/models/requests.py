"""Request models for lakehoused API.

Pydantic models for validating incoming API requests.
"""

from typing import Any

from pydantic import Field

from lakehoused.models.base import CamelCaseModel


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
