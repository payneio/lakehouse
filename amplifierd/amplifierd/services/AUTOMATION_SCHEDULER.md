# Automation Scheduler Service

The automation scheduler service manages scheduled execution of automations using APScheduler. It integrates with the AutomationManager and SessionManager to create sessions and send messages when automations trigger.

## Architecture

- **Scheduler**: APScheduler AsyncIOScheduler for async job scheduling
- **Schedule Types**: Supports cron, interval, and once schedules
- **Execution**: Creates sessions and sends messages on trigger
- **History**: Records execution history (success/failed)
- **Lifecycle**: Starts with daemon, reloads on updates, stops on shutdown

## Usage

The scheduler is automatically initialized when the daemon starts and is available via `app.state.automation_scheduler`.

### Accessing the Scheduler

```python
from fastapi import Request

@router.post("/automations/{automation_id}/schedule")
async def schedule_automation(automation_id: str, request: Request):
    scheduler = request.app.state.automation_scheduler
    automation = automation_manager.get_automation(automation_id)
    await scheduler.schedule_automation(automation)
```

### Schedule Types

#### Cron
Standard cron expressions (5 or 6 parts):
```python
ScheduleConfig(type="cron", value="0 9 * * *")  # Daily at 9 AM UTC
ScheduleConfig(type="cron", value="*/30 * * * *")  # Every 30 minutes
```

#### Interval
Duration string with unit (s/m/h/d):
```python
ScheduleConfig(type="interval", value="30m")  # Every 30 minutes
ScheduleConfig(type="interval", value="2h")   # Every 2 hours
ScheduleConfig(type="interval", value="1d")   # Every day
```

#### Once
ISO 8601 datetime string:
```python
ScheduleConfig(type="once", value="2024-12-15T09:00:00Z")  # One-time execution
```

## Execution Flow

1. **Trigger**: Automation triggers at scheduled time
2. **Load**: Automation and project metadata are loaded
3. **Session**: New session is created in automation's project
4. **Message**: Automation message is sent as user message
5. **Record**: Execution is recorded with status (success/failed)
6. **Next**: Next execution timestamp is calculated and saved

## Error Handling

- Failures are logged but don't crash the scheduler
- Failed executions are recorded with error messages
- Scheduler continues processing other automations
- Fire-and-forget approach (no retry logic)

## API Methods

### `start() -> None`
Initialize scheduler and load all enabled automations.

### `stop() -> None`
Gracefully shutdown scheduler, allowing running jobs to complete.

### `schedule_automation(automation: Automation) -> None`
Add or update automation job in scheduler. Disabled automations are removed.

### `unschedule_automation(automation_id: str) -> None`
Remove automation job from scheduler.

### `reload_all() -> None`
Clear scheduler and re-register all enabled automations.

## Integration Points

- **AutomationManager**: Persistence and execution history
- **SessionManager**: Session creation and lifecycle
- **AmplifiedDirectoryService**: Project metadata and profiles
- **MountPlanService**: Profile compilation for sessions

## Dependencies

- `apscheduler>=3.10.0` - Job scheduling library
- `amplifier_library` - Core automation and session management

## Testing

Comprehensive test suite in `tests/services/test_automation_scheduler.py` covering:
- Schedule parsing (cron, interval, once)
- Scheduler lifecycle (start, stop, idempotent)
- Automation scheduling (enabled, disabled, unschedule)
- Execution flow (session creation, message sending)
- Reload functionality

Run tests:
```bash
cd amplifierd
uv run pytest tests/services/test_automation_scheduler.py -v
```

## Implementation Philosophy

Follows the "ruthless simplicity" principle:
- No complex retry logic
- Fire-and-forget execution
- Simple error handling and logging
- Direct integration with existing services
- Minimal abstractions

## Future Enhancements

Potential improvements (not implemented):
- Retry logic for failed executions
- Execution throttling and rate limiting
- Advanced scheduling patterns (skip_if_running, etc.)
- Execution metrics and monitoring
- Notification on failures
