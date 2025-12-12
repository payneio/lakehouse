"""Automation models for scheduled workflows."""

from datetime import datetime
from typing import Literal

from pydantic import Field
from pydantic import field_validator

from amplifier_library.models.base import CamelCaseModel


class ScheduleConfig(CamelCaseModel):
    """Configuration for automation scheduling.

    Supports three schedule types:
    - cron: Standard cron expression (e.g., "0 9 * * *")
    - interval: Duration string (e.g., "1h", "30m", "1d")
    - once: ISO 8601 datetime string (e.g., "2024-12-15T09:00:00Z")
    """

    type: Literal["cron", "interval", "once"] = Field(description="Schedule type")
    value: str = Field(description="Schedule value (format depends on type)")

    @field_validator("value")
    @classmethod
    def validate_schedule_value(cls, v: str, info) -> str:
        """Validate schedule value matches type requirements.

        Args:
            v: Schedule value string
            info: Validation context containing schedule type

        Returns:
            Validated schedule value

        Raises:
            ValueError: If value format is invalid for schedule type
        """
        schedule_type = info.data.get("type")

        if schedule_type == "cron":
            # Basic cron validation - must have 5 or 6 parts
            parts = v.split()
            if len(parts) not in (5, 6):
                raise ValueError(f"Cron expression must have 5 or 6 parts, got {len(parts)}")

        elif schedule_type == "interval":
            # Validate interval format: <number><unit> where unit is s, m, h, d
            import re

            pattern = r"^\d+[smhd]$"
            if not re.match(pattern, v):
                raise ValueError(f"Interval must be format <number><unit> (s/m/h/d), got: {v}")

        elif schedule_type == "once":
            # Validate ISO 8601 datetime
            try:
                datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError as e:
                raise ValueError(f"Once schedule must be ISO 8601 datetime: {e}")

        return v


class Automation(CamelCaseModel):
    """Automation definition with scheduling information.

    Represents a scheduled workflow that runs automatically based on
    the configured schedule. Each automation executes in the context
    of a specific project (amplified directory).
    """

    id: str = Field(description="Unique automation identifier (UUID)")
    project_id: str = Field(description="Path to amplified directory")
    name: str = Field(description="Human-readable automation name")
    message: str = Field(description="Message to send to agent on execution")
    schedule: ScheduleConfig = Field(description="Schedule configuration")
    enabled: bool = Field(default=True, description="Whether automation is active")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    last_execution: datetime | None = Field(default=None, description="Last execution timestamp")
    next_execution: datetime | None = Field(default=None, description="Next scheduled execution timestamp")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate automation name is non-empty.

        Args:
            v: Automation name

        Returns:
            Validated name

        Raises:
            ValueError: If name is empty or only whitespace
        """
        if not v or not v.strip():
            raise ValueError("Automation name cannot be empty")
        return v.strip()


class ExecutionRecord(CamelCaseModel):
    """Record of an automation execution.

    Stored in JSONL format (one per line) for efficient append operations
    and historical analysis. Each execution creates a session that can be
    inspected using the session manager.
    """

    id: str = Field(description="Unique execution identifier")
    automation_id: str = Field(description="Automation that was executed")
    session_id: str = Field(description="Session ID for this execution")
    executed_at: datetime = Field(description="Execution timestamp")
    status: Literal["success", "failed"] = Field(description="Execution outcome")
    error: str | None = Field(default=None, description="Error message if failed")


class AutomationIndexEntry(CamelCaseModel):
    """Lightweight entry in automation index.

    Used for fast lookups without loading full automation data.
    Enables queries like "list all enabled automations" or
    "find automations by project".
    """

    automation_id: str = Field(description="Automation identifier")
    project_id: str = Field(description="Path to amplified directory")
    name: str = Field(description="Automation name")
    enabled: bool = Field(description="Whether automation is active")
    next_execution: datetime | None = Field(default=None, description="Next scheduled execution")


class AutomationIndex(CamelCaseModel):
    """Index of all automations for fast queries.

    Stored in state/automations/index.json and rebuilt on changes.
    Provides O(1) lookup by automation_id and enables fast filtering.
    """

    automations: dict[str, AutomationIndexEntry] = Field(
        default_factory=dict, description="Map of automation_id to index entry"
    )
    last_updated: datetime = Field(default_factory=datetime.now, description="Last index update timestamp")
