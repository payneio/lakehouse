# Automation Module

Storage and lifecycle management for scheduled automations.

## Overview

The automation module provides:
- **Automation persistence** - JSON storage with atomic writes
- **Execution tracking** - JSONL history for each automation
- **Fast indexing** - O(1) lookup and efficient filtering
- **Schedule validation** - Cron, interval, and one-time schedules

## Usage

```python
from pathlib import Path
from amplifier_library.automations import AutomationManager
from amplifier_library.models.automations import ScheduleConfig

# Initialize manager
manager = AutomationManager(storage_dir=Path(".amplifierd/state"))

# Create automation with cron schedule
schedule = ScheduleConfig(type="cron", value="0 9 * * *")  # Daily at 9 AM
automation = manager.create_automation(
    project_id="/home/user/project",
    name="Daily Report",
    message="Generate daily report",
    schedule=schedule,
    enabled=True
)

# List automations
all_automations = manager.list_automations()
project_automations = manager.list_automations(project_id="/home/user/project")
enabled_automations = manager.list_automations(enabled=True)

# Update automation
manager.update_automation(
    automation.id,
    enabled=False,
    schedule=ScheduleConfig(type="interval", value="2h")
)

# Record execution
manager.record_execution(
    automation_id=automation.id,
    session_id="session-123",
    status="success"
)

# Get execution history
history = manager.get_execution_history(automation.id, limit=10)
failed_runs = manager.get_execution_history(automation.id, status="failed")

# Delete automation
manager.delete_automation(automation.id)
```

## Schedule Types

### Cron
Standard cron expressions (5 or 6 parts):
```python
ScheduleConfig(type="cron", value="0 9 * * *")        # Daily at 9 AM
ScheduleConfig(type="cron", value="*/15 * * * *")     # Every 15 minutes
ScheduleConfig(type="cron", value="0 0 * * 0")        # Weekly on Sunday
```

### Interval
Duration strings (number + unit):
```python
ScheduleConfig(type="interval", value="30s")  # Every 30 seconds
ScheduleConfig(type="interval", value="5m")   # Every 5 minutes
ScheduleConfig(type="interval", value="2h")   # Every 2 hours
ScheduleConfig(type="interval", value="1d")   # Every day
```

### Once
ISO 8601 datetime string:
```python
ScheduleConfig(type="once", value="2024-12-15T09:00:00Z")
ScheduleConfig(type="once", value="2024-12-15T09:00:00+00:00")
```

## Storage Structure

```
.amplifierd/state/automations/
├── index.json                     # Fast lookup index
├── {automation_id}.json           # Individual automation files
└── executions/
    └── {automation_id}.jsonl      # Execution history (append-only)
```

## Data Models

### Automation
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "projectId": "/home/user/project",
    "name": "Daily Report",
    "message": "Generate daily report",
    "schedule": {
        "type": "cron",
        "value": "0 9 * * *"
    },
    "enabled": true,
    "createdAt": "2024-12-12T00:00:00Z",
    "updatedAt": "2024-12-12T00:00:00Z",
    "lastExecution": null,
    "nextExecution": "2024-12-12T09:00:00Z"
}
```

### ExecutionRecord
```python
{
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "automationId": "550e8400-e29b-41d4-a716-446655440000",
    "sessionId": "session-123",
    "executedAt": "2024-12-12T09:00:00Z",
    "status": "success",
    "error": null
}
```

## Error Handling

The manager provides clear error messages:
- **Duplicate names** - Within same project
- **Invalid schedules** - Format validation
- **Missing projects** - Project directory must exist
- **Not found** - When updating/deleting non-existent automation

## Implementation Notes

- **Atomic writes** - Uses tmp + rename pattern for reliability
- **JSONL format** - Execution history is append-only
- **Index maintenance** - Automatically updated on changes
- **Validation** - Pydantic models with custom validators
- **Logging** - All operations logged at appropriate levels
