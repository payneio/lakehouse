"""Test that profile switching correctly updates session tools.

This test verifies the fix for the bug where profile switching saved the mount_plan
to disk but didn't update the SessionStreamManager, causing the session to continue
using the old profile's tools.
"""

import pytest

from lakehoused.services.session_stream_manager import SessionStreamManager
from lakehoused.services.session_stream_registry import SessionStreamRegistry


@pytest.mark.asyncio
async def test_session_stream_manager_update_mount_plan(tmp_path) -> None:
    """Test SessionStreamManager.update_mount_plan() updates config and invalidates runner."""
    # Initial mount plan
    initial_mount_plan = {
        "tools": [
            {"name": "tool-search", "source": "registry://tools/tool-search"},
        ]
    }

    # Create mock resolver
    from unittest.mock import Mock

    mock_resolver = Mock()
    mock_resolver.async_resolve = Mock()

    # Create manager
    session_id = "test-session"
    manager = SessionStreamManager(session_id, initial_mount_plan, mock_resolver)

    # Verify initial state
    assert manager.mount_plan == initial_mount_plan
    assert manager._runner is None

    # Simulate creating a runner by directly setting it
    # (Normally happens on first message, but requires full session setup)
    from lakehoused.execution.runner import ExecutionRunner
    from lakehoused.sessions.manager import SessionManager

    session_manager = SessionManager(tmp_path)

    manager._runner = ExecutionRunner(
        session_manager=session_manager, config=initial_mount_plan, session_id=session_id, resolver=mock_resolver
    )
    manager._runner_initialized = True
    original_runner = manager._runner
    assert manager._runner is not None

    # Update mount plan (simulates profile change)
    new_mount_plan = {
        "tools": [
            {"name": "tool-search", "source": "registry://tools/tool-search"},
            {"name": "tool-filesystem", "source": "registry://tools/tool-filesystem"},
            {"name": "tool-bash", "source": "registry://tools/tool-bash"},
        ]
    }

    await manager.update_mount_plan(new_mount_plan)

    # Verify mount plan was updated
    assert manager.mount_plan == new_mount_plan
    assert len(manager.mount_plan["tools"]) == 3

    # Verify runner was invalidated
    assert manager._runner is None
    assert manager._runner_initialized is False

    # Verify new runner can be created with new mount plan
    # (Just verify it's None and would be recreated, don't actually create it)
    assert manager.mount_plan is new_mount_plan


@pytest.mark.asyncio
async def test_session_stream_registry_update_mount_plan() -> None:
    """Test SessionStreamRegistry.update_mount_plan() updates existing manager."""
    from unittest.mock import Mock

    registry = SessionStreamRegistry()

    initial_mount_plan = {
        "tools": [{"name": "tool-search", "source": "registry://tools/tool-search"}]
    }

    session_id = "test-session-2"

    # Create mock resolver
    mock_resolver = Mock()
    mock_resolver.async_resolve = Mock()

    # Create manager
    manager = await registry.get_or_create(session_id, initial_mount_plan, mock_resolver)
    assert manager.mount_plan == initial_mount_plan

    # Update via registry
    new_mount_plan = {
        "tools": [
            {"name": "tool-search", "source": "registry://tools/tool-search"},
            {"name": "tool-bash", "source": "registry://tools/tool-bash"},
        ]
    }

    await registry.update_mount_plan(session_id, new_mount_plan)

    # Verify manager was updated
    same_manager = registry.get(session_id)
    assert same_manager is manager  # Same instance
    assert manager.mount_plan == new_mount_plan


@pytest.mark.asyncio
async def test_session_stream_registry_update_nonexistent_session() -> None:
    """Test updating mount plan for non-existent session does nothing."""
    registry = SessionStreamRegistry()

    new_mount_plan = {"tools": [{"name": "tool-bash"}]}

    # Should not raise exception
    await registry.update_mount_plan("nonexistent-session", new_mount_plan)
