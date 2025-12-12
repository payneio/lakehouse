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

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from amplifier_library.automations.manager import AutomationManager
from amplifier_library.models.automations import Automation
from amplifier_library.sessions.manager import SessionManager

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
    ) -> None:
        """Initialize automation scheduler.

        Args:
            automation_manager: Manager for automation persistence
            session_manager: Manager for session lifecycle
        """
        self.automation_manager = automation_manager
        self.session_manager = session_manager
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False

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
            CronTrigger configured with expression

        Example:
            "0 9 * * *" -> Daily at 9:00 AM UTC
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
                timezone="UTC",
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
                timezone="UTC",
            )
        raise ValueError(f"Invalid cron expression (must be 5 or 6 parts): {cron_expr}")

    def _parse_interval(self, interval_str: str) -> IntervalTrigger:
        """Parse interval string into IntervalTrigger.

        Args:
            interval_str: Duration string (e.g., "30m", "2h", "1d")

        Returns:
            IntervalTrigger configured with interval

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

        return IntervalTrigger(seconds=seconds, timezone="UTC")

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
            DateTrigger for one-time execution

        Example:
            "2024-12-15T09:00:00Z" -> Execute once at that time
        """
        # Parse ISO datetime (handle Z suffix)
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        return DateTrigger(run_date=dt, timezone="UTC")

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
            execution_date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
            session_name = f"{automation.name} - {execution_date}"

            # Create session in automation's project
            # Note: We need to load the amplified directory metadata to get the default profile
            from amplifier_library.config.loader import load_config

            from ..services.amplified_directory_service import AmplifiedDirectoryService

            config = load_config()
            data_path = Path(config.data_path)
            amplified_service = AmplifiedDirectoryService(data_path)

            amplified_dir = amplified_service.get(automation.project_id)
            if not amplified_dir:
                raise ValueError(f"Project directory not amplified: {automation.project_id}")

            profile_name = amplified_dir.metadata.get("default_profile")
            if not profile_name:
                raise ValueError(f"No default_profile set for project: {automation.project_id}")

            # Get absolute path for mount plan generation
            absolute_amplified_dir = str((data_path / automation.project_id).resolve())

            # Generate mount plan
            from amplifier_library.storage import get_share_dir

            from ..services.mount_plan_service import MountPlanService

            share_dir = get_share_dir()
            mount_plan_service = MountPlanService(share_dir)
            mount_plan = mount_plan_service.generate_mount_plan(profile_name, Path(absolute_amplified_dir))

            # Add session metadata
            if "session" not in mount_plan:
                mount_plan["session"] = {}
            if "settings" not in mount_plan["session"]:
                mount_plan["session"]["settings"] = {}

            mount_plan["session"]["settings"]["amplified_dir"] = absolute_amplified_dir
            mount_plan["session"]["settings"]["profile_name"] = profile_name
            mount_plan["session"]["settings"]["automation_id"] = automation_id

            # Create session with meaningful name
            self.session_manager.create_session(
                session_id=session_id,
                profile_name=profile_name,
                mount_plan=mount_plan,
                amplified_dir=automation.project_id,
                name=session_name,
            )

            # Start session
            self.session_manager.start_session(session_id)

            # Convert to library SessionMetadata for execution
            from amplifier_library.models.sessions import SessionMetadata as LibrarySessionMetadata

            session_metadata = self.session_manager.get_session(session_id)
            if not session_metadata:
                raise ValueError(f"Session {session_id} not found after creation")

            session = LibrarySessionMetadata(**session_metadata.model_dump())

            # Resolve runtime mentions
            from ..services.mention_resolver import MentionResolver

            compiled_profile_dir = share_dir / "profiles" / profile_name
            resolver = MentionResolver(
                compiled_profile_dir=compiled_profile_dir,
                amplified_dir=Path(absolute_amplified_dir),
                data_dir=data_path,
            )
            runtime_context_messages = resolver.resolve_runtime_mentions(automation.message)
            logger.info(f"Resolved {len(runtime_context_messages)} runtime context messages")

            # Get stream manager (creates if needed)
            from ..services.session_stream_registry import get_stream_registry

            registry = get_stream_registry()
            manager = await registry.get_or_create(session_id, mount_plan)

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
