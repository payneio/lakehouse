"""Tests for automation scheduler service."""

from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from amplifier_library.automations.manager import AutomationManager
from amplifier_library.models.automations import ScheduleConfig
from amplifier_library.sessions.manager import SessionManager
from amplifierd.services.automation_scheduler import AutomationScheduler


@pytest.fixture
def automation_manager(tmp_path: Path) -> AutomationManager:
    """Create AutomationManager with temporary storage."""
    return AutomationManager(storage_dir=tmp_path)


@pytest.fixture
def session_manager(tmp_path: Path) -> SessionManager:
    """Create SessionManager with temporary storage."""
    return SessionManager(storage_dir=tmp_path / "sessions")


@pytest.fixture
def scheduler(automation_manager: AutomationManager, session_manager: SessionManager) -> AutomationScheduler:
    """Create AutomationScheduler instance."""
    return AutomationScheduler(
        automation_manager=automation_manager,
        session_manager=session_manager,
    )


class TestScheduleParsing:
    """Test schedule configuration parsing."""

    def test_parse_cron_standard(self, scheduler: AutomationScheduler) -> None:
        """Test parsing standard 5-part cron expression."""
        trigger = scheduler._parse_cron("0 9 * * *")
        assert trigger is not None

    def test_parse_cron_extended(self, scheduler: AutomationScheduler) -> None:
        """Test parsing extended 6-part cron expression."""
        trigger = scheduler._parse_cron("0 0 9 * * *")
        assert trigger is not None

    def test_parse_interval_minutes(self, scheduler: AutomationScheduler) -> None:
        """Test parsing interval in minutes."""
        trigger = scheduler._parse_interval("30m")
        assert trigger.interval.total_seconds() == 1800  # 30 * 60

    def test_parse_interval_hours(self, scheduler: AutomationScheduler) -> None:
        """Test parsing interval in hours."""
        trigger = scheduler._parse_interval("2h")
        assert trigger.interval.total_seconds() == 7200  # 2 * 3600

    def test_parse_interval_days(self, scheduler: AutomationScheduler) -> None:
        """Test parsing interval in days."""
        trigger = scheduler._parse_interval("1d")
        assert trigger.interval.total_seconds() == 86400  # 24 * 3600

    def test_parse_once(self, scheduler: AutomationScheduler) -> None:
        """Test parsing one-time datetime."""
        dt_str = "2024-12-15T09:00:00Z"
        trigger = scheduler._parse_once(dt_str)
        assert trigger.run_date.year == 2024
        assert trigger.run_date.month == 12
        assert trigger.run_date.day == 15


class TestSchedulerLifecycle:
    """Test scheduler startup and shutdown."""

    async def test_start_scheduler(self, scheduler: AutomationScheduler) -> None:
        """Test scheduler starts successfully."""
        await scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()

    async def test_stop_scheduler(self, scheduler: AutomationScheduler) -> None:
        """Test scheduler stops successfully."""
        await scheduler.start()
        await scheduler.stop()
        assert scheduler._running is False

    async def test_start_idempotent(self, scheduler: AutomationScheduler) -> None:
        """Test starting scheduler multiple times is safe."""
        await scheduler.start()
        await scheduler.start()  # Should not raise
        assert scheduler._running is True
        await scheduler.stop()


class TestAutomationScheduling:
    """Test automation scheduling operations."""

    async def test_schedule_enabled_automation(
        self,
        scheduler: AutomationScheduler,
        automation_manager: AutomationManager,
        tmp_path: Path,
    ) -> None:
        """Test scheduling an enabled automation."""
        # Create test automation
        (tmp_path / "test_project").mkdir()
        automation = automation_manager.create_automation(
            project_id=str(tmp_path / "test_project"),
            name="Test Automation",
            message="Test message",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=True,
        )

        await scheduler.start()

        # Schedule automation
        await scheduler.schedule_automation(automation)

        # Verify job was added
        job = scheduler.scheduler.get_job(automation.id)
        assert job is not None
        assert job.name == f"Automation: {automation.name}"

        await scheduler.stop()

    async def test_schedule_disabled_automation(
        self,
        scheduler: AutomationScheduler,
        automation_manager: AutomationManager,
        tmp_path: Path,
    ) -> None:
        """Test scheduling a disabled automation removes it."""
        # Create test automation
        (tmp_path / "test_project").mkdir()
        automation = automation_manager.create_automation(
            project_id=str(tmp_path / "test_project"),
            name="Test Automation",
            message="Test message",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=False,
        )

        await scheduler.start()

        # Schedule automation (should remove from scheduler)
        await scheduler.schedule_automation(automation)

        # Verify job was not added
        job = scheduler.scheduler.get_job(automation.id)
        assert job is None

        await scheduler.stop()

    async def test_unschedule_automation(
        self,
        scheduler: AutomationScheduler,
        automation_manager: AutomationManager,
        tmp_path: Path,
    ) -> None:
        """Test unscheduling removes automation from scheduler."""
        # Create and schedule automation
        (tmp_path / "test_project").mkdir()
        automation = automation_manager.create_automation(
            project_id=str(tmp_path / "test_project"),
            name="Test Automation",
            message="Test message",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=True,
        )

        await scheduler.start()
        await scheduler.schedule_automation(automation)

        # Unschedule
        await scheduler.unschedule_automation(automation.id)

        # Verify job was removed
        job = scheduler.scheduler.get_job(automation.id)
        assert job is None

        await scheduler.stop()


class TestAutomationExecution:
    """Test automation execution flow."""

    @pytest.mark.skip(reason="Needs update for bundle system")
    async def test_execute_automation_creates_session(
        self,
        scheduler: AutomationScheduler,
        automation_manager: AutomationManager,
        session_manager: SessionManager,
        tmp_path: Path,
    ) -> None:
        """Test automation execution creates session and sends message."""
        # Create amplified directory structure
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / ".amplified").mkdir()
        (project_dir / ".amplified" / "metadata.json").write_text(
            '{"default_profile": "foundation/foundation"}'
        )

        # Create automation
        automation = automation_manager.create_automation(
            project_id=str(project_dir),
            name="Test Automation",
            message="Test automation message",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=True,
        )

        # Mock dependencies (using correct import paths from _execute_automation)
        with (
            patch("amplifierd.services.amplified_directory_service.AmplifiedDirectoryService") as mock_amplified_service,
            patch("amplifierd.services.mount_plan_service.MountPlanService") as mock_mount_plan_service,
            patch("amplifier_library.config.loader.load_config") as mock_config,
            patch("amplifier_library.storage.get_share_dir") as mock_share_dir,
            patch("amplifierd.services.session_stream_registry.get_stream_registry") as mock_registry,
            patch("amplifierd.services.mention_resolver.MentionResolver") as mock_resolver,
        ):
            # Setup mocks
            mock_config.return_value.data_path = str(tmp_path)
            mock_share_dir.return_value = tmp_path / "share"

            mock_amplified = MagicMock()
            mock_amplified.metadata = {"default_profile": "foundation/foundation"}

            # Mock the AmplifiedDirectoryService instance and its get method
            mock_service_instance = MagicMock()
            mock_service_instance.get.return_value = mock_amplified
            mock_amplified_service.return_value = mock_service_instance

            mock_mount_plan_service.return_value.generate_mount_plan.return_value = {
                "session": {
                    "settings": {},
                    "orchestrator": {
                        "module": "orchestrator/sequential-orchestrator",
                        "source": "registry",
                    },
                    "context": {
                        "module": "context/simple-context",
                        "source": "registry",
                    },
                },
                "tools": [],
            }

            # Mock mention resolver
            mock_resolver_instance = MagicMock()
            mock_resolver_instance.resolve_runtime_mentions.return_value = []
            mock_resolver.return_value = mock_resolver_instance

            # Mock stream registry and runner
            mock_manager = MagicMock()
            mock_runner = MagicMock()

            # Mock the async execute_stream method to return empty async generator
            async def mock_execute_stream(*args, **kwargs):
                yield "Test response"

            mock_runner.execute_stream = mock_execute_stream
            mock_runner._session = MagicMock()
            mock_manager.get_runner = AsyncMock(return_value=mock_runner)
            mock_manager.mount_hooks = AsyncMock()

            mock_registry_instance = MagicMock()
            mock_registry_instance.get_or_create = AsyncMock(return_value=mock_manager)
            mock_registry.return_value = mock_registry_instance

            # Execute automation
            await scheduler._execute_automation(automation.id)

            # Verify execution was recorded
            history = automation_manager.get_execution_history(automation.id)
            assert len(history) == 1
            assert history[0].status == "success"
            assert history[0].session_id.startswith("auto_")


class TestReloadAll:
    """Test reloading all automations."""

    async def test_reload_schedules_all_enabled(
        self,
        scheduler: AutomationScheduler,
        automation_manager: AutomationManager,
        tmp_path: Path,
    ) -> None:
        """Test reload_all schedules all enabled automations."""
        # Create multiple automations
        (tmp_path / "project1").mkdir()
        (tmp_path / "project2").mkdir()

        auto1 = automation_manager.create_automation(
            project_id=str(tmp_path / "project1"),
            name="Automation 1",
            message="Message 1",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=True,
        )

        auto2 = automation_manager.create_automation(
            project_id=str(tmp_path / "project2"),
            name="Automation 2",
            message="Message 2",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
        )

        # Disabled automation should not be scheduled
        automation_manager.create_automation(
            project_id=str(tmp_path / "project1"),
            name="Disabled Automation",
            message="Message 3",
            schedule=ScheduleConfig(type="interval", value="2h"),
            enabled=False,
        )

        await scheduler.start()

        # Verify both enabled automations are scheduled
        job1 = scheduler.scheduler.get_job(auto1.id)
        job2 = scheduler.scheduler.get_job(auto2.id)

        assert job1 is not None
        assert job2 is not None

        await scheduler.stop()
