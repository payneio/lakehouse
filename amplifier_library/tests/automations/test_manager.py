"""Tests for AutomationManager."""

import tempfile
from pathlib import Path

import pytest

from amplifier_library.automations.manager import AutomationManager
from amplifier_library.models.automations import ScheduleConfig


@pytest.fixture
def storage_dir():
    """Create temporary storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def project_dir(tmp_path):
    """Create temporary project directory."""
    project = tmp_path / "test_project"
    project.mkdir()
    return project


@pytest.fixture
def manager(storage_dir):
    """Create AutomationManager instance."""
    return AutomationManager(storage_dir)


def test_create_automation(manager, project_dir):
    """Test creating an automation."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    automation = manager.create_automation(
        project_id=str(project_dir),
        name="Daily Report",
        message="Generate daily report",
        schedule=schedule,
        enabled=True,
    )

    assert automation.id is not None
    assert automation.project_id == str(project_dir)
    assert automation.name == "Daily Report"
    assert automation.message == "Generate daily report"
    assert automation.schedule.type == "cron"
    assert automation.enabled is True
    assert automation.last_execution is None


def test_get_automation(manager, project_dir):
    """Test retrieving an automation."""
    schedule = ScheduleConfig(type="interval", value="1h")

    created = manager.create_automation(
        project_id=str(project_dir),
        name="Hourly Sync",
        message="Sync data",
        schedule=schedule,
    )

    retrieved = manager.get_automation(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Hourly Sync"


def test_get_nonexistent_automation(manager):
    """Test getting automation that doesn't exist."""
    result = manager.get_automation("nonexistent-id")
    assert result is None


def test_list_automations(manager, project_dir):
    """Test listing automations."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    # Create multiple automations
    manager.create_automation(
        project_id=str(project_dir),
        name="Automation 1",
        message="Message 1",
        schedule=schedule,
    )
    manager.create_automation(
        project_id=str(project_dir),
        name="Automation 2",
        message="Message 2",
        schedule=schedule,
        enabled=False,
    )

    # List all
    all_automations = manager.list_automations()
    assert len(all_automations) == 2

    # Filter by project
    project_automations = manager.list_automations(project_id=str(project_dir))
    assert len(project_automations) == 2

    # Filter by enabled
    enabled_automations = manager.list_automations(enabled=True)
    assert len(enabled_automations) == 1
    assert enabled_automations[0].name == "Automation 1"


def test_update_automation(manager, project_dir):
    """Test updating an automation."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    automation = manager.create_automation(
        project_id=str(project_dir),
        name="Original Name",
        message="Original message",
        schedule=schedule,
    )

    updated = manager.update_automation(
        automation.id,
        name="Updated Name",
        enabled=False,
    )

    assert updated.name == "Updated Name"
    assert updated.enabled is False
    assert updated.message == "Original message"  # Unchanged


def test_delete_automation(manager, project_dir):
    """Test deleting an automation."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    automation = manager.create_automation(
        project_id=str(project_dir),
        name="To Delete",
        message="Message",
        schedule=schedule,
    )

    # Verify it exists
    assert manager.get_automation(automation.id) is not None

    # Delete it
    result = manager.delete_automation(automation.id)
    assert result is True

    # Verify it's gone
    assert manager.get_automation(automation.id) is None


def test_duplicate_name_validation(manager, project_dir):
    """Test that duplicate names within a project are rejected."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    manager.create_automation(
        project_id=str(project_dir),
        name="Duplicate Name",
        message="Message 1",
        schedule=schedule,
    )

    with pytest.raises(ValueError, match="already exists"):
        manager.create_automation(
            project_id=str(project_dir),
            name="Duplicate Name",
            message="Message 2",
            schedule=schedule,
        )


def test_record_execution(manager, project_dir):
    """Test recording execution history."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    automation = manager.create_automation(
        project_id=str(project_dir),
        name="Test Automation",
        message="Test message",
        schedule=schedule,
    )

    # Record successful execution
    record = manager.record_execution(
        automation_id=automation.id,
        session_id="session-123",
        status="success",
    )

    assert record.automation_id == automation.id
    assert record.session_id == "session-123"
    assert record.status == "success"
    assert record.error is None


def test_get_execution_history(manager, project_dir):
    """Test retrieving execution history."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    automation = manager.create_automation(
        project_id=str(project_dir),
        name="Test Automation",
        message="Test message",
        schedule=schedule,
    )

    # Record multiple executions
    manager.record_execution(automation.id, "session-1", "success")
    manager.record_execution(automation.id, "session-2", "failed", error="Test error")
    manager.record_execution(automation.id, "session-3", "success")

    # Get all history
    history = manager.get_execution_history(automation.id)
    assert len(history) == 3
    assert history[0].session_id == "session-3"  # Newest first

    # Filter by status
    failed_history = manager.get_execution_history(automation.id, status="failed")
    assert len(failed_history) == 1
    assert failed_history[0].session_id == "session-2"
    assert failed_history[0].error == "Test error"


def test_schedule_validation():
    """Test schedule configuration validation."""
    # Valid cron
    ScheduleConfig(type="cron", value="0 9 * * *")

    # Valid interval
    ScheduleConfig(type="interval", value="1h")
    ScheduleConfig(type="interval", value="30m")

    # Valid once
    ScheduleConfig(type="once", value="2024-12-15T09:00:00Z")

    # Invalid cron
    with pytest.raises(ValueError, match="5 or 6 parts"):
        ScheduleConfig(type="cron", value="invalid")

    # Invalid interval
    with pytest.raises(ValueError, match="format"):
        ScheduleConfig(type="interval", value="invalid")

    # Invalid once
    with pytest.raises(ValueError, match="ISO 8601"):
        ScheduleConfig(type="once", value="invalid")


def test_index_management(manager, project_dir):
    """Test that index is properly maintained."""
    schedule = ScheduleConfig(type="cron", value="0 9 * * *")

    # Create automation
    automation = manager.create_automation(
        project_id=str(project_dir),
        name="Test Automation",
        message="Test message",
        schedule=schedule,
    )

    # Verify index exists
    index = manager._load_index()
    assert automation.id in index.automations
    assert index.automations[automation.id].name == "Test Automation"

    # Delete automation
    manager.delete_automation(automation.id)

    # Verify removed from index
    index = manager._load_index()
    assert automation.id not in index.automations
