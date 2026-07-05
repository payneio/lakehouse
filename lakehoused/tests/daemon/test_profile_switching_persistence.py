"""Test that bundle switching correctly persists mount plan to disk."""

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from lakehoused.models.sessions import SessionMetadata
from lakehoused.models.sessions import SessionStatus
from lakehoused.routers.sessions import change_session_bundle


@pytest.fixture
def mock_state_dir(tmp_path: Path) -> Path:
    """Create temporary state directory structure.

    Args:
        tmp_path: pytest temporary directory fixture

    Returns:
        Path to state directory
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    # Create session directory
    session_id = "test_session_123"
    session_dir = state_dir / "sessions" / session_id
    session_dir.mkdir(parents=True)

    # Write initial mount plan with bundle A
    initial_mount_plan = {
        "format_version": "1.0",
        "session": {
            "session_id": session_id,
            "settings": {
                "bundle_name": "foundation/base",
            },
        },
        "tools": [
            {"name": "bash", "config": {"working_dir": "/some/path"}},
        ],
    }
    mount_plan_path = session_dir / "mount_plan.json"
    with open(mount_plan_path, "w") as f:
        json.dump(initial_mount_plan, f, indent=2)

    return state_dir


@pytest.fixture
def mock_session_metadata(mock_state_dir: Path) -> SessionMetadata:
    """Create mock session metadata.

    Args:
        mock_state_dir: Fixture providing state directory

    Returns:
        SessionMetadata for testing
    """
    return SessionMetadata(
        session_id="test_session_123",
        status=SessionStatus.ACTIVE,
        bundle_name="foundation/base",
        mount_plan_path="mount_plan.json",
        project_path="test-project",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def new_mount_plan() -> dict:
    """Create new mount plan for production bundle.

    Returns:
        Mount plan dict for production bundle
    """
    return {
        "format_version": "1.0",
        "session": {
            "session_id": "test_session_123",
            "settings": {
                "bundle_name": "foundation/production",
            },
        },
        "tools": [
            {"name": "bash", "config": {"working_dir": "/different/path"}},
            {"name": "grep", "config": {"working_dir": "/different/path"}},
        ],
    }


@pytest.fixture
def mock_bundle_manager(new_mount_plan: dict, tmp_path: Path) -> Mock:
    """Create mock LakehouseBundleManager.

    Args:
        new_mount_plan: New mount plan to return
        tmp_path: pytest temporary directory fixture

    Returns:
        Mock bundle manager
    """
    mock_manager = Mock()
    mock_manager.bundles_dir = tmp_path / "bundles"
    mock_manager.home_dir = tmp_path

    async def mock_generate_mount_plan(*args, **kwargs):
        return new_mount_plan

    mock_manager.generate_mount_plan = mock_generate_mount_plan
    return mock_manager


@pytest.mark.asyncio
async def test_bundle_change_persists_mount_plan_to_disk(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
    mock_bundle_manager: Mock,
) -> None:
    """Test that changing bundle saves new mount plan to mount_plan.json.

    This test verifies the fix for the bug where bundle changes were applied
    to the ExecutionRunner but not persisted to disk, causing subsequent
    messages to load the old bundle from mount_plan.json.

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for bundle B
        mock_bundle_manager: Mock bundle manager
    """
    session_id = "test_session_123"
    mount_plan_path = mock_state_dir / "sessions" / session_id / "mount_plan.json"

    # Verify initial mount plan exists with base bundle
    with open(mount_plan_path) as f:
        initial_plan = json.load(f)
    assert initial_plan["session"]["settings"]["bundle_name"] == "foundation/base"
    assert len(initial_plan["tools"]) == 1

    # Mock services
    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)
    mock_session_service.storage_dir = mock_state_dir / "sessions"

    def update_session_side_effect(session_id: str, update_fn):  # type: ignore[no-untyped-def]
        update_fn(mock_session_metadata)

    mock_session_service._update_session = Mock(side_effect=update_session_side_effect)

    with (
        patch("lakehoused.routers.sessions.get_state_dir", return_value=mock_state_dir),
        patch(
            "lakehoused.bundles.LakehouseBundleManager",
            return_value=mock_bundle_manager,
        ),
    ):
        # Call the endpoint
        result = await change_session_bundle(
            session_id=session_id,
            session_service=mock_session_service,
            bundle_name="foundation/production",
        )

    # Verify the result metadata was updated
    assert result.bundle_name == "foundation/production"

    # CRITICAL: Verify mount_plan.json was updated on disk
    with open(mount_plan_path) as f:
        updated_plan = json.load(f)

    assert updated_plan["session"]["settings"]["bundle_name"] == "foundation/production"
    assert len(updated_plan["tools"]) == 2  # New bundle has 2 tools
    assert updated_plan["tools"][0]["name"] == "bash"
    assert updated_plan["tools"][1]["name"] == "grep"


@pytest.mark.asyncio
async def test_bundle_change_handles_file_write_error(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
    mock_bundle_manager: Mock,
) -> None:
    """Test that file write errors are handled gracefully.

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for bundle B
        mock_bundle_manager: Mock bundle manager
    """
    session_id = "test_session_123"

    # Mock services
    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)
    mock_session_service.storage_dir = mock_state_dir / "sessions"

    # Make the mount plan directory read-only to cause write error
    session_dir = mock_state_dir / "sessions" / session_id
    session_dir.chmod(0o444)

    try:
        with (
            patch("lakehoused.routers.sessions.get_state_dir", return_value=mock_state_dir),
            patch(
                "lakehoused.bundles.LakehouseBundleManager",
                return_value=mock_bundle_manager,
            ),
        ):
            # Expect HTTP 500 error due to file write failure
            with pytest.raises(HTTPException) as exc_info:
                await change_session_bundle(
                    session_id=session_id,
                    session_service=mock_session_service,
                    bundle_name="foundation/production",
                )

            assert exc_info.value.status_code == 500
    finally:
        # Restore permissions for cleanup
        session_dir.chmod(0o755)


@pytest.mark.asyncio
async def test_bundle_change_with_no_active_runner(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
    mock_bundle_manager: Mock,
) -> None:
    """Test that bundle change works even when there's no active ExecutionRunner.

    This verifies that the mount plan is still persisted to disk even if the
    ExecutionRunner doesn't exist yet (which is a valid scenario).

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for bundle B
        mock_bundle_manager: Mock bundle manager
    """
    session_id = "test_session_123"
    mount_plan_path = mock_state_dir / "sessions" / session_id / "mount_plan.json"

    # Mock services
    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)
    mock_session_service.storage_dir = mock_state_dir / "sessions"

    def update_session_side_effect(session_id: str, update_fn):  # type: ignore[no-untyped-def]
        update_fn(mock_session_metadata)

    mock_session_service._update_session = Mock(side_effect=update_session_side_effect)

    with (
        patch("lakehoused.routers.sessions.get_state_dir", return_value=mock_state_dir),
        patch(
            "lakehoused.bundles.LakehouseBundleManager",
            return_value=mock_bundle_manager,
        ),
    ):
        # Call should succeed even though there's no runner
        result = await change_session_bundle(
            session_id=session_id,
            session_service=mock_session_service,
            bundle_name="foundation/production",
        )

    # Verify metadata was updated
    assert result.bundle_name == "foundation/production"

    # CRITICAL: Verify mount_plan.json was still updated
    with open(mount_plan_path) as f:
        updated_plan = json.load(f)

    assert updated_plan["session"]["settings"]["bundle_name"] == "foundation/production"
