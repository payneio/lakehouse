"""Automation scheduler service for amplifierd.

Manages scheduled execution of automations using APScheduler.
Integrates with AutomationManager and SessionManager to create sessions
and send messages when automations trigger.

Architecture:
- Uses APScheduler AsyncIOScheduler for async job scheduling
- Parses schedule configurations (cron, interval, once)
- Creates sessions and sends messages on trigger
- Records execution history (success/failed)
- Lifecycle: start with daemon, reload on updates, stop on shutdown
"""

import logging
import re
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from lakehouse_library.automations.manager import AutomationManager
from lakehouse_library.models.automations import Automation
from lakehouse_library.sessions.manager import SessionManager

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Manages automation scheduling and execution.

    Uses APScheduler to trigger automations at configured times.
    Creates sessions and sends messages to execute automation workflows.
    """

    def __init__(
        self,
        automation_manager: AutomationManager,
        session_manager: SessionManager,
        timezone: str = "UTC",
        module_resolver: Any = None,
    ) -> None:
        """Initialize automation scheduler.

        Args:
            automation_manager: Manager for automation persistence
            session_manager: Manager for session lifecycle
            timezone: IANA timezone identifier for scheduling (e.g., "America/Los_Angeles")
            module_resolver: BundleModuleResolver from Foundation (daemon-level)
        """
        self.automation_manager = automation_manager
        self.session_manager = session_manager
        self.timezone = timezone
        self.module_resolver = module_resolver
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self._running = False
        logger.info(f"Automation scheduler initialized with timezone: {timezone}")

    async def start(self) -> None:
        """Start scheduler and load all enabled automations.

        Initializes the APScheduler and registers all enabled automations
        as jobs. Idempotent - safe to call multiple times.
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting automation scheduler")
        self.scheduler.start()
        self._running = True

        # Load and schedule all enabled automations
        await self.reload_all()

        logger.info("Automation scheduler started successfully")

    async def stop(self) -> None:
        """Stop scheduler gracefully.

        Shuts down APScheduler, allowing running jobs to complete.
        """
        if not self._running:
            logger.warning("Scheduler not running")
            return

        logger.info("Stopping automation scheduler")
        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("Automation scheduler stopped")

    async def schedule_automation(self, automation: Automation) -> None:
        """Add or update automation job in scheduler.

        Parses the automation's schedule configuration and registers
        it with APScheduler. Replaces existing job if already scheduled.

        Args:
            automation: Automation to schedule

        Raises:
            ValueError: If schedule configuration is invalid
        """
        if not automation.enabled:
            # Remove from scheduler if disabled
            await self.unschedule_automation(automation.id)
            logger.info(f"Automation {automation.id} disabled, removed from scheduler")
            return

        try:
            # Parse schedule into APScheduler trigger
            trigger = self._parse_schedule(automation.schedule.type, automation.schedule.value)

            # Calculate next execution time
            next_fire_time = trigger.get_next_fire_time(None, datetime.now(UTC))

            # Update automation with next execution time
            self.automation_manager.update_automation(
                automation.id,
                next_execution=next_fire_time,
            )

            # Add job to scheduler (replace=True handles updates)
            self.scheduler.add_job(
                func=self._execute_automation,
                trigger=trigger,
                args=[automation.id],
                id=automation.id,
                name=f"Automation: {automation.name}",
                replace_existing=True,
            )

            logger.info(
                f"Scheduled automation {automation.id} ('{automation.name}') - next execution: {next_fire_time}"
            )

        except Exception as e:
            logger.error(f"Failed to schedule automation {automation.id}: {e}")
            raise

    async def unschedule_automation(self, automation_id: str) -> None:
        """Remove automation job from scheduler.

        Args:
            automation_id: Automation to remove
        """
        try:
            self.scheduler.remove_job(automation_id)
            logger.info(f"Unscheduled automation {automation_id}")
        except Exception:
            # Job not found - that's okay
            pass

    async def reload_all(self) -> None:
        """Reload all enabled automations.

        Clears scheduler and re-registers all enabled automations.
        Used on startup and after bulk updates.
        """
        logger.info("Reloading all automations")

        # Clear all existing jobs
        self.scheduler.remove_all_jobs()

        # Load and schedule all enabled automations
        automations = self.automation_manager.list_automations(enabled=True)

        for automation in automations:
            try:
                await self.schedule_automation(automation)
            except Exception as e:
                logger.error(f"Failed to reload automation {automation.id}: {e}")
                # Continue with other automations

        logger.info(f"Reloaded {len(automations)} enabled automations")

    async def execute_now(self, automation_id: str) -> str:
        """Execute automation immediately, bypassing schedule.

        Creates session and runs automation message on-demand.
        Useful for testing automations or running them manually.

        Args:
            automation_id: Automation to execute

        Returns:
            Session ID that was created

        Raises:
            ValueError: If automation not found or invalid
        """
        logger.info(f"Manual execution requested for automation {automation_id}")

        # Verify automation exists
        automation = self.automation_manager.get_automation(automation_id)
        if automation is None:
            raise ValueError(f"Automation {automation_id} not found")

        # Execute using existing private method
        await self._execute_automation(automation_id)

        # Get the session ID from the most recent execution
        executions = self.automation_manager.get_execution_history(automation_id=automation_id, limit=1)
        if not executions:
            raise ValueError(f"Automation {automation_id} executed but no session created")

        session_id = executions[0].session_id
        logger.info(f"Manual execution of automation {automation_id} created session {session_id}")
        return session_id

    def _parse_schedule(self, schedule_type: str, value: str):
        """Parse schedule configuration into APScheduler trigger.

        Args:
            schedule_type: Type of schedule (cron, interval, once)
            value: Schedule value (format depends on type)

        Returns:
            APScheduler trigger object

        Raises:
            ValueError: If schedule format is invalid
        """
        if schedule_type == "cron":
            return self._parse_cron(value)
        if schedule_type == "interval":
            return self._parse_interval(value)
        if schedule_type == "once":
            return self._parse_once(value)
        raise ValueError(f"Unknown schedule type: {schedule_type}")

    def _parse_cron(self, cron_expr: str) -> CronTrigger:
        """Parse cron expression into CronTrigger.

        Args:
            cron_expr: Standard cron expression (5 or 6 parts)

        Returns:
            CronTrigger configured with expression in scheduler's timezone

        Example:
            "0 9 * * *" -> Daily at 9:00 AM in configured timezone
            "*/30 * * * *" -> Every 30 minutes
        """
        parts = cron_expr.split()

        if len(parts) == 5:
            # Standard cron: minute hour day month day_of_week
            minute, hour, day, month, day_of_week = parts
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=self.timezone,
            )
        if len(parts) == 6:
            # Extended cron with seconds: second minute hour day month day_of_week
            second, minute, hour, day, month, day_of_week = parts
            return CronTrigger(
                second=second,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=self.timezone,
            )
        raise ValueError(f"Invalid cron expression (must be 5 or 6 parts): {cron_expr}")

    def _parse_interval(self, interval_str: str) -> IntervalTrigger:
        """Parse interval string into IntervalTrigger.

        Args:
            interval_str: Duration string (e.g., "30m", "2h", "1d")

        Returns:
            IntervalTrigger configured with interval in scheduler's timezone

        Example:
            "30m" -> Every 30 minutes
            "2h" -> Every 2 hours
            "1d" -> Every day
        """
        # Extract number and unit
        match = re.match(r"^(\d+)([smhd])$", interval_str)
        if not match:
            raise ValueError(f"Invalid interval format: {interval_str}")

        value = int(match.group(1))
        unit = match.group(2)

        # Convert to seconds
        seconds = self._interval_to_seconds(value, unit)

        return IntervalTrigger(seconds=seconds, timezone=self.timezone)

    def _interval_to_seconds(self, value: int, unit: str) -> int:
        """Convert interval notation to seconds.

        Args:
            value: Numeric value
            unit: Time unit (s, m, h, d)

        Returns:
            Total seconds
        """
        if unit == "s":
            return value
        if unit == "m":
            return value * 60
        if unit == "h":
            return value * 3600
        if unit == "d":
            return value * 86400
        raise ValueError(f"Unknown interval unit: {unit}")

    def _parse_once(self, datetime_str: str) -> DateTrigger:
        """Parse ISO datetime into DateTrigger.

        Args:
            datetime_str: ISO 8601 datetime string

        Returns:
            DateTrigger for one-time execution in scheduler's timezone

        Example:
            "2024-12-15T09:00:00Z" -> Execute once at that time
        """
        # Parse ISO datetime (handle Z suffix)
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return DateTrigger(run_date=dt, timezone=self.timezone)

    async def _execute_automation(self, automation_id: str) -> None:
        """Execute automation by creating session and sending message.

        This is called by APScheduler when an automation triggers.
        Creates a new session in the automation's project, sends
        the automation message as a user message, and executes it.

        Args:
            automation_id: Automation to execute
        """
        logger.info(f"Executing automation {automation_id}")

        try:
            # Load automation
            automation = self.automation_manager.get_automation(automation_id)
            if automation is None:
                logger.error(f"Automation {automation_id} not found")
                return

            # Generate session ID and name
            import uuid

            session_id = f"auto_{uuid.uuid4().hex[:8]}"

            # Create human-readable session name: "{automation_name} - {date}"
            # Use configured timezone for display instead of UTC
            from zoneinfo import ZoneInfo

            local_tz = ZoneInfo(self.timezone)
            execution_time = datetime.now(local_tz)
            # Format timezone abbreviation (e.g., "PST", "EST", "UTC")
            tz_abbrev = execution_time.strftime("%Z")
            execution_date = execution_time.strftime(f"%Y-%m-%d %H:%M {tz_abbrev}")
            session_name = f"{automation.name} - {execution_date}"

            # Create session in automation's project
            # Note: We need to load the project metadata to get the default bundle
            from lakehouse_library.config.loader import load_config

            from ..services.project_service import ProjectService

            config = load_config()
            data_path = Path(config.data_path)
            project_service = ProjectService(data_path)

            project = project_service.get(automation.project_id)
            if not project:
                raise ValueError(f"Project directory not found: {automation.project_id}")

            # Get bundle name from project metadata (try default_bundle, fallback to default_bundle)
            bundle_name = project.metadata.get("default_bundle") or project.metadata.get("default_bundle")
            if not bundle_name:
                raise ValueError(f"No default_bundle set for project: {automation.project_id}")

            # Get absolute path for mount plan generation
            absolute_project_path = str((data_path / automation.project_id).resolve())

            # Generate mount plan using bundle manager
            from lakehouse_library.bundles import LakehouseBundleManager

            from ..config.loader import load_secrets

            bundle_manager = LakehouseBundleManager()

            # Load secrets for API key injection
            secrets = load_secrets()
            api_key = next(iter(secrets.api_keys.values()), None) if secrets.api_keys else None

            mount_plan = await bundle_manager.generate_mount_plan(
                bundle_ref=bundle_name,
                session_id=session_id,
                project_path=absolute_project_path,
                api_key=api_key,
            )

            # Note: Runtime config (working_dir, allowed_write_paths, API keys, log paths)
            # is already injected by bundle_manager.generate_mount_plan()

            # Add session metadata
            if "session" not in mount_plan:
                mount_plan["session"] = {}
            if "settings" not in mount_plan["session"]:
                mount_plan["session"]["settings"] = {}

            mount_plan["session"]["settings"]["project_path"] = absolute_project_path
            mount_plan["session"]["settings"]["bundle_name"] = bundle_name
            mount_plan["session"]["settings"]["automation_id"] = automation_id

            # Create session with meaningful name (marked as created by automation)
            self.session_manager.create_session(
                session_id=session_id,
                bundle_name=bundle_name,
                mount_plan=mount_plan,
                project_path=automation.project_id,
                name=session_name,
                created_by="automation",  # Mark as automation-created for unread tracking
            )

            # Start session (no-op since sessions start as ACTIVE, but kept for compatibility)
            self.session_manager.start_session(session_id)

            # Emit session:created event
            from ..models.events import SessionCreatedEvent
            from ..services.global_events import GlobalEventService

            session_metadata = self.session_manager.get_session(session_id)
            if session_metadata:
                await GlobalEventService.emit(
                    SessionCreatedEvent(
                        session_id=session_id,
                        session_name=session_metadata.name,
                        project_id=automation.project_id,
                        is_unread=session_metadata.is_unread,
                        created_by="automation",
                    )
                )

            # Convert to library SessionMetadata for execution
            from lakehouse_library.models.sessions import SessionMetadata as LibrarySessionMetadata

            session_metadata = self.session_manager.get_session(session_id)
            if not session_metadata:
                raise ValueError(f"Session {session_id} not found after creation")

            session = LibrarySessionMetadata(**session_metadata.model_dump())

            # Resolve runtime mentions
            from ..services.mention_resolver import MentionResolver

            bundle_dir = bundle_manager.bundles_dir / bundle_name
            resolver = MentionResolver(
                compiled_profile_dir=bundle_dir,
                project_path=Path(absolute_project_path),
                data_dir=data_path,
            )
            runtime_context_messages = resolver.resolve_runtime_mentions(automation.message)
            logger.info(f"Resolved {len(runtime_context_messages)} runtime context messages")

            # Get stream manager (creates if needed)
            from ..services.session_stream_registry import get_stream_registry

            registry = get_stream_registry()
            manager = await registry.get_or_create(session_id, mount_plan, self.module_resolver)

            # Get runner
            runner = await manager.get_runner(session)

            # Mount hooks if needed
            if runner._session is not None:
                await manager.mount_hooks(runner)

            # Execute the message (this saves messages to transcript)
            logger.info(f"Executing automation message for {automation_id} in session {session_id}")
            full_response = ""
            async for token in runner.execute_stream(session, automation.message, runtime_context_messages):
                full_response += token

            logger.info(f"Automation {automation_id} execution complete - response length: {len(full_response)}")

            # Record successful execution
            self.automation_manager.record_execution(
                automation_id=automation_id,
                session_id=session_id,
                status="success",
            )

            # Update next_execution timestamp
            trigger = self._parse_schedule(automation.schedule.type, automation.schedule.value)
            next_fire_time = trigger.get_next_fire_time(None, datetime.now(UTC))
            self.automation_manager.update_automation(
                automation_id,
                next_execution=next_fire_time,
            )

            logger.info(
                f"Automation {automation_id} executed successfully - session {session_id} - "
                f"next execution: {next_fire_time}"
            )

        except Exception as e:
            logger.error(f"Automation {automation_id} execution failed: {e}", exc_info=True)

            # Record failed execution
            try:
                self.automation_manager.record_execution(
                    automation_id=automation_id,
                    session_id="",  # No session created
                    status="failed",
                    error=str(e),
                )
            except Exception as record_error:
                logger.error(f"Failed to record execution failure: {record_error}")
