"""Execution trace models for session activity visualization.

These models represent the structure of execution turns as displayed
in the frontend ExecutionPanel. They are populated by aggregating
events from events.jsonl (single source of truth).
"""

from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class TraceTool(BaseModel):
    """Tool call trace data."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    name: str = ""
    parallel_group_id: str = Field(default="", serialization_alias="parallelGroupId")
    status: str = "starting"
    start_time: int = Field(default=0, serialization_alias="startTime")
    end_time: int | None = Field(default=None, serialization_alias="endTime")
    duration: float | None = None
    arguments: dict[str, Any] | None = None
    result: str | None = None
    error: str | None = None
    is_sub_agent: bool = Field(default=False, serialization_alias="isSubAgent")
    sub_agent_name: str | None = Field(default=None, serialization_alias="subAgentName")
    child_session_id: str | None = Field(default=None, serialization_alias="childSessionId")


class TraceThinking(BaseModel):
    """Thinking block trace data."""

    id: str = ""
    content: str = ""
    timestamp: int = 0


class TraceTurn(BaseModel):
    """Turn trace data representing one user message + assistant response cycle."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    user_message: str = Field(default="", serialization_alias="userMessage")
    assistant_message_id: str | None = Field(default=None, serialization_alias="assistantMessageId")
    status: str = "active"
    start_time: int = Field(default=0, serialization_alias="startTime")
    end_time: int | None = Field(default=None, serialization_alias="endTime")
    tools: list[TraceTool] = Field(default_factory=list)
    thinking: list[TraceThinking] = Field(default_factory=list)
