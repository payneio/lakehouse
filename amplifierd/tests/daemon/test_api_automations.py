"""Integration tests for automation API endpoints.

Tests cover:
- Lifecycle: create, update, delete, toggle automations
- Queries: list, get, filter by enabled status
- Execution history: record and query execution records
- Scheduler integration: schedule/unschedule/reschedule
- Validation: cron expressions, duplicate names, project existence
- Error handling: 404s, 400s, 500s
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from amplifier_library.models.automations import Automation
from amplifier_library.models.automations import ExecutionRecord
from amplifier_library.models.automations import ScheduleConfig
from amplifierd.main import app
from amplifierd.routers.automations import get_automation_manager
from amplifierd.routers.automations import get_automation_scheduler


@pytest.fixture
def mock_automation() -> Automation:
    """Sample automation for testing.

    Returns:
        Automation with cron schedule
    """
    return Automation(
        id="auto-123",
        project_id="test-project",
        name="Daily Report",
        message="Generate daily status report",
        schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
        enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_execution=None,
        next_execution=None,
    )


@pytest.fixture
def mock_disabled_automation() -> Automation:
    """Sample disabled automation for testing.

    Returns:
        Automation with interval schedule, disabled
    """
    return Automation(
        id="auto-456",
        project_id="test-project",
        name="Hourly Backup",
        message="Backup project data",
        schedule=ScheduleConfig(type="interval", value="1h"),
        enabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_execution=None,
        next_execution=None,
    )


@pytest.fixture
def mock_execution_record() -> ExecutionRecord:
    """Sample execution record for testing.

    Returns:
        ExecutionRecord with success status
    """
    return ExecutionRecord(
        id="exec-123",
        automation_id="auto-123",
        session_id="session-789",
        executed_at=datetime.now(UTC),
        status="success",
        error=None,
    )


@pytest.fixture
def mock_automation_manager(mock_automation: Automation, mock_disabled_automation: Automation) -> Mock:
    """Mock AutomationManager with common behaviors.

    Args:
        mock_automation: Sample automation fixture
        mock_disabled_automation: Sample disabled automation fixture

    Returns:
        Mock AutomationManager
    """
    manager = Mock()
    manager.create_automation = Mock(return_value=mock_automation)
    manager.get_automation = Mock(return_value=mock_automation)
    manager.list_automations = Mock(return_value=[mock_automation, mock_disabled_automation])
    manager.update_automation = Mock(return_value=mock_automation)
    manager.delete_automation = Mock(return_value=True)
    manager.get_execution_history = Mock(return_value=[])
    return manager


@pytest.fixture
def mock_automation_scheduler() -> AsyncMock:
    """Mock AutomationScheduler with async methods.

    Returns:
        AsyncMock scheduler
    """
    scheduler = AsyncMock()
    scheduler.schedule_automation = AsyncMock()
    scheduler.unschedule_automation = AsyncMock()
    return scheduler


@pytest.fixture
def mock_project_exists(monkeypatch, tmp_path):
    """Mock project path validation and config to use temp directory.

    Args:
        monkeypatch: Pytest monkeypatch fixture
        tmp_path: Pytest temp directory fixture
    """
    # Create a test project directory
    test_project_dir = tmp_path / "test-project"
    test_project_dir.mkdir(parents=True, exist_ok=True)

    # Mock load_config to return config with our tmp_path as data_path
    from amplifier_library.config.settings import DaemonSettings

    mock_config = DaemonSettings(
        host="127.0.0.1",
        port=8420,
        data_path=str(tmp_path),
        log_level="info",
    )

    # Patch at the location where it's imported in the automations module
    import amplifier_library.config.loader

    monkeypatch.setattr(amplifier_library.config.loader, "load_config", lambda: mock_config)


@pytest.fixture
def override_services(
    mock_automation_manager: Mock,
    mock_automation_scheduler: AsyncMock,
    mock_project_exists,
):
    """Override dependencies with mocks.

    Args:
        mock_automation_manager: Mock manager
        mock_automation_scheduler: Mock scheduler
        mock_project_exists: Mock project validation

    Yields:
        None - dependencies are overridden in app
    """
    app.dependency_overrides[get_automation_manager] = lambda: mock_automation_manager
    # get_automation_scheduler takes a Request parameter, so we need to accept it
    app.dependency_overrides[get_automation_scheduler] = lambda request=None: mock_automation_scheduler
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_services) -> TestClient:
    """FastAPI test client with mocked dependencies.

    Args:
        override_services: Dependency override fixture

    Returns:
        Test client
    """
    return TestClient(app)


@pytest.mark.integration
class TestAutomationLifecycle:
    """Test automation lifecycle endpoints (create, update, delete, toggle)."""

    # --- Create Tests ---

    def test_create_automation_with_cron_schedule(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test POST /automations/ creates automation with cron schedule."""
        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Daily Report",
                "message": "Generate daily status report",
                "schedule": {"type": "cron", "value": "0 9 * * *"},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["automation"]["id"] == "auto-123"
        assert data["automation"]["name"] == "Daily Report"
        assert data["automation"]["schedule"]["type"] == "cron"
        assert data["automation"]["enabled"] is True

        mock_automation_manager.create_automation.assert_called_once_with(
            project_id="test-project",
            name="Daily Report",
            message="Generate daily status report",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
        )

    def test_create_automation_disabled(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test POST /automations/ with enabled=false does not schedule."""
        # Mock manager to return disabled automation
        disabled_automation = Automation(
            id="auto-disabled",
            project_id="test-project",
            name="Disabled Task",
            message="This won't run",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.create_automation.return_value = disabled_automation

        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Disabled Task",
                "message": "This won't run",
                "schedule": {"type": "interval", "value": "1h"},
                "enabled": False,
            },
        )

        assert response.status_code == 201

        # Scheduler should NOT be called for disabled automation
        mock_automation_scheduler.schedule_automation.assert_not_called()

    def test_create_automation_with_interval_schedule(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test POST /automations/ creates automation with interval schedule."""
        # Mock manager to return automation with interval schedule
        interval_automation = Automation(
            id="auto-interval",
            project_id="test-project",
            name="Hourly Task",
            message="Run every hour",
            schedule=ScheduleConfig(type="interval", value="1h"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.create_automation.return_value = interval_automation

        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Hourly Task",
                "message": "Run every hour",
                "schedule": {"type": "interval", "value": "1h"},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["automation"]["schedule"]["type"] == "interval"
        assert data["automation"]["schedule"]["value"] == "1h"

    def test_create_automation_with_once_schedule(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test POST /automations/ creates automation with once schedule."""
        future_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

        # Mock manager to return automation with once schedule
        once_automation = Automation(
            id="auto-once",
            project_id="test-project",
            name="One Time Task",
            message="Run once at specific time",
            schedule=ScheduleConfig(type="once", value=future_time),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.create_automation.return_value = once_automation

        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "One Time Task",
                "message": "Run once at specific time",
                "schedule": {"type": "once", "value": future_time},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["automation"]["schedule"]["type"] == "once"

    def test_create_automation_invalid_cron_expression(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test POST /automations/ returns 422 for invalid cron expression (validation error)."""
        # Invalid cron expression is caught by Pydantic validation before hitting manager
        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Bad Cron",
                "message": "Invalid schedule",
                "schedule": {"type": "cron", "value": "invalid"},
                "enabled": True,
            },
        )

        # Pydantic validation returns 422
        assert response.status_code == 422
        # Check that error mentions the cron validation issue
        detail = response.json()["detail"]
        assert any("5 or 6 parts" in str(error) for error in detail)

    def test_create_automation_duplicate_name_in_project(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test POST /automations/ returns 400 for duplicate name within project."""
        # Mock manager to raise ValueError for duplicate name
        mock_automation_manager.create_automation.side_effect = ValueError(
            "Automation with name 'Daily Report' already exists"
        )

        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Daily Report",
                "message": "Duplicate name",
                "schedule": {"type": "cron", "value": "0 9 * * *"},
                "enabled": True,
            },
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_automation_project_not_found(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test POST /automations/ returns 500 when project doesn't exist.

        Note: The endpoint raises HTTPException(404) but it gets caught by the generic
        exception handler and converted to 500. This is the current implementation behavior.
        """
        # Reset the side_effect from previous test
        mock_automation_manager.create_automation.side_effect = None
        mock_automation_manager.create_automation.return_value = None

        # Try to create automation for non-existent project
        # (tmp_path has test-project but not nonexistent-project)
        response = client.post(
            "/api/v1/projects/nonexistent-project/automations/",
            json={
                "name": "Test",
                "message": "Test",
                "schedule": {"type": "cron", "value": "0 9 * * *"},
                "enabled": True,
            },
        )

        # Currently returns 500 (could be improved to return 404)
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

    def test_create_automation_calls_scheduler_when_enabled(
        self, client: TestClient, mock_automation_scheduler: AsyncMock, mock_automation: Automation
    ) -> None:
        """Test POST /automations/ calls scheduler when automation is enabled."""
        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Scheduled Task",
                "message": "Should be scheduled",
                "schedule": {"type": "cron", "value": "0 9 * * *"},
                "enabled": True,
            },
        )

        assert response.status_code == 201

        # Verify scheduler was called with the created automation
        mock_automation_scheduler.schedule_automation.assert_called_once()
        call_args = mock_automation_scheduler.schedule_automation.call_args
        assert call_args[0][0].id == mock_automation.id

    # --- Update Tests ---

    def test_update_automation_schedule(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test PATCH /automations/{id} updates schedule and reschedules."""
        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"schedule": {"type": "interval", "value": "2h"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["automation"]["id"] == "auto-123"

        # Verify manager was called with schedule update
        mock_automation_manager.update_automation.assert_called_once()
        call_kwargs = mock_automation_manager.update_automation.call_args[1]
        assert "schedule" in call_kwargs

        # Verify scheduler was called to reschedule
        mock_automation_scheduler.schedule_automation.assert_called_once()

    def test_update_automation_name(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test PATCH /automations/{id} updates name."""
        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"name": "New Name"},
        )

        assert response.status_code == 200

        mock_automation_manager.update_automation.assert_called_once()
        call_kwargs = mock_automation_manager.update_automation.call_args[1]
        assert call_kwargs["name"] == "New Name"

    def test_update_automation_message(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test PATCH /automations/{id} updates message."""
        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"message": "New message content"},
        )

        assert response.status_code == 200

        mock_automation_manager.update_automation.assert_called_once()
        call_kwargs = mock_automation_manager.update_automation.call_args[1]
        assert call_kwargs["message"] == "New message content"

    def test_update_automation_schedules_when_enabling(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test PATCH /automations/{id} schedules automation when enabling."""
        # Mock manager to return automation with enabled=True after update
        updated_automation = Automation(
            id="auto-123",
            project_id="test-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.update_automation.return_value = updated_automation

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"enabled": True},
        )

        assert response.status_code == 200

        # Verify scheduler was called to schedule the automation
        mock_automation_scheduler.schedule_automation.assert_called_once()

    def test_update_automation_unschedules_when_disabling(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test PATCH /automations/{id} unschedules automation when disabling."""
        # Mock manager to return automation with enabled=False after update
        updated_automation = Automation(
            id="auto-123",
            project_id="test-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.update_automation.return_value = updated_automation

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"enabled": False},
        )

        assert response.status_code == 200

        # Verify scheduler was called to unschedule
        mock_automation_scheduler.unschedule_automation.assert_called_once_with("auto-123")

    def test_update_automation_not_found(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test PATCH /automations/{id} returns 404 for missing automation."""
        mock_automation_manager.get_automation.return_value = None

        response = client.patch(
            "/api/v1/projects/test-project/automations/nonexistent",
            json={"name": "New Name"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_automation_wrong_project(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation: Automation
    ) -> None:
        """Test PATCH /automations/{id} returns 404 when automation belongs to different project."""
        # Mock automation with different project_id
        wrong_project_automation = Automation(
            id="auto-123",
            project_id="different-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.get_automation.return_value = wrong_project_automation

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"name": "New Name"},
        )

        assert response.status_code == 404
        assert "test-project" in response.json()["detail"]

    def test_update_automation_no_changes(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation: Automation
    ) -> None:
        """Test PATCH /automations/{id} returns existing automation when no changes."""
        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["automation"]["id"] == "auto-123"

        # Manager should not call update when no changes
        mock_automation_manager.update_automation.assert_not_called()

    # --- Delete Tests ---

    def test_delete_automation_success(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test DELETE /automations/{id} deletes automation."""
        response = client.delete("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 204

        # Verify scheduler unscheduled first
        mock_automation_scheduler.unschedule_automation.assert_called_once_with("auto-123")

        # Verify manager deleted automation
        mock_automation_manager.delete_automation.assert_called_once_with("auto-123")

    def test_delete_automation_calls_unschedule_first(
        self, client: TestClient, mock_automation_scheduler: AsyncMock, mock_automation_manager: Mock
    ) -> None:
        """Test DELETE /automations/{id} calls unschedule before deleting."""
        # Track call order
        calls = []
        mock_automation_scheduler.unschedule_automation.side_effect = lambda x: calls.append("unschedule")
        mock_automation_manager.delete_automation.side_effect = lambda x: calls.append("delete") or True

        response = client.delete("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 204
        assert calls == ["unschedule", "delete"]

    def test_delete_automation_not_found(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test DELETE /automations/{id} returns 404 for missing automation."""
        mock_automation_manager.get_automation.return_value = None

        response = client.delete("/api/v1/projects/test-project/automations/nonexistent")

        assert response.status_code == 404

    def test_delete_automation_wrong_project(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation: Automation
    ) -> None:
        """Test DELETE /automations/{id} returns 404 when automation belongs to different project."""
        # Mock automation with different project_id
        wrong_project_automation = Automation(
            id="auto-123",
            project_id="different-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.get_automation.return_value = wrong_project_automation

        response = client.delete("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 404
        assert "test-project" in response.json()["detail"]

    def test_delete_automation_continues_if_unschedule_fails(
        self, client: TestClient, mock_automation_scheduler: AsyncMock, mock_automation_manager: Mock
    ) -> None:
        """Test DELETE /automations/{id} continues deletion even if unscheduling fails."""
        # Mock scheduler to raise exception
        mock_automation_scheduler.unschedule_automation.side_effect = Exception("Scheduler error")

        response = client.delete("/api/v1/projects/test-project/automations/auto-123")

        # Deletion should still succeed
        assert response.status_code == 204
        mock_automation_manager.delete_automation.assert_called_once()

    # --- Toggle Tests ---

    def test_toggle_automation_enable(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test PATCH /automations/{id}/toggle enables automation."""
        # Mock manager to return enabled automation
        enabled_automation = Automation(
            id="auto-123",
            project_id="test-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.update_automation.return_value = enabled_automation

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123/toggle",
            json={"enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["automation_id"] == "auto-123"
        assert data["enabled"] is True

        # Verify scheduler was called
        mock_automation_scheduler.schedule_automation.assert_called_once()

    def test_toggle_automation_disable(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation_scheduler: AsyncMock
    ) -> None:
        """Test PATCH /automations/{id}/toggle disables automation."""
        # Mock manager to return disabled automation
        disabled_automation = Automation(
            id="auto-123",
            project_id="test-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.update_automation.return_value = disabled_automation

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123/toggle",
            json={"enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

        # Verify scheduler was called to unschedule
        mock_automation_scheduler.unschedule_automation.assert_called_once_with("auto-123")

    def test_toggle_automation_not_found(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test PATCH /automations/{id}/toggle returns 404 for missing automation."""
        mock_automation_manager.get_automation.return_value = None

        response = client.patch(
            "/api/v1/projects/test-project/automations/nonexistent/toggle",
            json={"enabled": True},
        )

        assert response.status_code == 404


@pytest.mark.integration
class TestAutomationQueries:
    """Test automation query endpoints (list, get, filter)."""

    def test_list_automations_no_filters(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/ returns all automations."""
        response = client.get("/api/v1/projects/test-project/automations/")

        assert response.status_code == 200
        data = response.json()
        assert "automations" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["automations"]) == 2

        mock_automation_manager.list_automations.assert_called_once_with(project_id="test-project", enabled=None)

    def test_list_automations_filter_enabled(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/?enabled=true filters by enabled status."""
        response = client.get("/api/v1/projects/test-project/automations/?enabled=true")

        assert response.status_code == 200

        mock_automation_manager.list_automations.assert_called_once_with(project_id="test-project", enabled=True)

    def test_list_automations_filter_disabled(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/?enabled=false filters by disabled status."""
        response = client.get("/api/v1/projects/test-project/automations/?enabled=false")

        assert response.status_code == 200

        mock_automation_manager.list_automations.assert_called_once_with(project_id="test-project", enabled=False)

    def test_list_automations_with_pagination(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/ applies limit and offset."""
        response = client.get("/api/v1/projects/test-project/automations/?limit=10&offset=5")

        assert response.status_code == 200
        data = response.json()
        # Total should be full count before pagination
        assert data["total"] == 2

    def test_list_automations_empty_result(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/ returns empty list when no automations."""
        mock_automation_manager.list_automations.return_value = []

        response = client.get("/api/v1/projects/test-project/automations/")

        assert response.status_code == 200
        data = response.json()
        assert data["automations"] == []
        assert data["total"] == 0

    def test_get_automation_by_id(self, client: TestClient, mock_automation: Automation) -> None:
        """Test GET /automations/{id} returns specific automation."""
        response = client.get("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 200
        data = response.json()
        assert data["automation"]["id"] == "auto-123"
        assert data["automation"]["name"] == mock_automation.name

    def test_get_automation_not_found(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/{id} returns 404 for missing automation."""
        mock_automation_manager.get_automation.return_value = None

        response = client.get("/api/v1/projects/test-project/automations/nonexistent")

        assert response.status_code == 404

    def test_get_automation_wrong_project(
        self, client: TestClient, mock_automation_manager: Mock, mock_automation: Automation
    ) -> None:
        """Test GET /automations/{id} returns 404 when automation belongs to different project."""
        # Mock automation with different project_id
        wrong_project_automation = Automation(
            id="auto-123",
            project_id="different-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.get_automation.return_value = wrong_project_automation

        response = client.get("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 404
        assert "test-project" in response.json()["detail"]


@pytest.mark.integration
class TestExecutionHistory:
    """Test execution history query endpoints."""

    def test_get_execution_history_success(
        self, client: TestClient, mock_automation_manager: Mock, mock_execution_record: ExecutionRecord
    ) -> None:
        """Test GET /automations/{id}/executions returns execution history."""
        mock_automation_manager.get_execution_history.return_value = [mock_execution_record]

        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions")

        assert response.status_code == 200
        data = response.json()
        assert "executions" in data
        assert "total" in data
        assert len(data["executions"]) == 1
        assert data["executions"][0]["id"] == "exec-123"

        mock_automation_manager.get_execution_history.assert_called()

    def test_get_execution_history_filter_status(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/{id}/executions?status=success filters by status."""
        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions?status=success")

        assert response.status_code == 200

        # Verify filter was passed to manager
        call_kwargs = mock_automation_manager.get_execution_history.call_args[1]
        assert call_kwargs["status"] == "success"

    def test_get_execution_history_with_pagination(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/{id}/executions applies limit and offset."""
        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions?limit=20&offset=10")

        assert response.status_code == 200

        # Verify pagination parameters - the endpoint calls get_execution_history twice:
        # once with pagination params and once with limit=10000 for total count
        # Check that at least one call had the correct parameters
        calls = mock_automation_manager.get_execution_history.call_args_list
        assert any(
            call[1]["limit"] == 20 and call[1]["offset"] == 10 for call in calls
        ), f"Expected call with limit=20, offset=10 in {calls}"

    def test_get_execution_history_automation_not_found(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/{id}/executions returns 404 for missing automation."""
        mock_automation_manager.get_automation.return_value = None

        response = client.get("/api/v1/projects/test-project/automations/nonexistent/executions")

        assert response.status_code == 404

    def test_get_execution_history_wrong_project(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/{id}/executions returns 404 for wrong project."""
        # Mock automation with different project_id
        wrong_project_automation = Automation(
            id="auto-123",
            project_id="different-project",
            name="Test",
            message="Test",
            schedule=ScheduleConfig(type="cron", value="0 9 * * *"),
            enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        mock_automation_manager.get_automation.return_value = wrong_project_automation

        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions")

        assert response.status_code == 404
        assert "test-project" in response.json()["detail"]

    def test_get_execution_history_empty(self, client: TestClient, mock_automation_manager: Mock) -> None:
        """Test GET /automations/{id}/executions returns empty list when no executions."""
        mock_automation_manager.get_execution_history.return_value = []

        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions")

        assert response.status_code == 200
        data = response.json()
        assert data["executions"] == []
        assert data["total"] == 0


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_create_automation_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test POST /automations/ returns 500 for unexpected errors."""
        mock_automation_manager.create_automation.side_effect = Exception("Unexpected error")

        response = client.post(
            "/api/v1/projects/test-project/automations/",
            json={
                "name": "Test",
                "message": "Test",
                "schedule": {"type": "cron", "value": "0 9 * * *"},
                "enabled": True,
            },
        )

        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"]

    def test_update_automation_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test PATCH /automations/{id} returns 500 for unexpected errors."""
        mock_automation_manager.update_automation.side_effect = Exception("Unexpected error")

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123",
            json={"name": "New Name"},
        )

        assert response.status_code == 500

    def test_delete_automation_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test DELETE /automations/{id} returns 500 for unexpected errors."""
        mock_automation_manager.delete_automation.side_effect = Exception("Unexpected error")

        response = client.delete("/api/v1/projects/test-project/automations/auto-123")

        assert response.status_code == 500

    def test_list_automations_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/ returns 500 for unexpected errors."""
        mock_automation_manager.list_automations.side_effect = Exception("Unexpected error")

        response = client.get("/api/v1/projects/test-project/automations/")

        assert response.status_code == 500

    def test_toggle_automation_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test PATCH /automations/{id}/toggle returns 500 for unexpected errors."""
        mock_automation_manager.update_automation.side_effect = Exception("Unexpected error")

        response = client.patch(
            "/api/v1/projects/test-project/automations/auto-123/toggle",
            json={"enabled": True},
        )

        assert response.status_code == 500

    def test_get_execution_history_unexpected_error(
        self, client: TestClient, mock_automation_manager: Mock
    ) -> None:
        """Test GET /automations/{id}/executions returns 500 for unexpected errors."""
        mock_automation_manager.get_execution_history.side_effect = Exception("Unexpected error")

        response = client.get("/api/v1/projects/test-project/automations/auto-123/executions")

        assert response.status_code == 500
