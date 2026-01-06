"""Test that profile switching correctly persists mount plan to disk."""

import json
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifierd.routers.sessions import change_session_profile


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

    # Write initial mount plan with profile A
    initial_mount_plan = {
        "format_version": "1.0",
        "session": {
            "session_id": session_id,
            "settings": {
                "profile_name": "foundation/base",
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
        profile_name="foundation/base",
        mount_plan_path="mount_plan.json",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def new_mount_plan() -> dict:
    """Create new mount plan for production profile.

    Returns:
        Mount plan dict for production profile
    """
    return {
        "format_version": "1.0",
        "session": {
            "session_id": "test_session_123",
            "settings": {
                "profile_name": "foundation/production",
            },
        },
        "tools": [
            {"name": "bash", "config": {"working_dir": "/different/path"}},
            {"name": "grep", "config": {"working_dir": "/different/path"}},
        ],
    }


@pytest.mark.skip(reason="Needs update for bundle system")
@pytest.mark.asyncio
async def test_profile_change_persists_mount_plan_to_disk(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
) -> None:
    """Test that changing profile saves new mount plan to mount_plan.json.

    This test verifies the fix for the bug where profile changes were applied
    to the ExecutionRunner but not persisted to disk, causing subsequent
    messages to load the old profile from mount_plan.json.

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for profile B
    """
    session_id = "test_session_123"
    mount_plan_path = mock_state_dir / "sessions" / session_id / "mount_plan.json"

    # Verify initial mount plan exists with base profile
    with open(mount_plan_path) as f:
        initial_plan = json.load(f)
    assert initial_plan["session"]["settings"]["profile_name"] == "foundation/base"
    assert len(initial_plan["tools"]) == 1

    # Mock services
    mock_mount_plan_service = Mock()
    mock_mount_plan_service.generate_mount_plan = Mock(return_value=new_mount_plan)

    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)

    def update_session_side_effect(session_id: str, update_fn):  # type: ignore[no-untyped-def]
        update_fn(mock_session_metadata)

    mock_session_service._update_session = Mock(side_effect=update_session_side_effect)

    # Patch the change_session_profile function to avoid ExecutionRunner issues
    with (
        patch("amplifierd.routers.sessions.get_state_dir", return_value=mock_state_dir),
        patch("amplifierd.routers.sessions.change_session_profile", new_callable=AsyncMock),
    ):
        # Call the endpoint
        result = await change_session_profile(
            session_id=session_id,
            mount_plan_service=mock_mount_plan_service,
            session_service=mock_session_service,
            profile_name="foundation/production",
        )

    # Verify the result metadata was updated
    assert result.profile_name == "foundation/production"

    # CRITICAL: Verify mount_plan.json was updated on disk
    with open(mount_plan_path) as f:
        updated_plan = json.load(f)

    assert updated_plan["session"]["settings"]["profile_name"] == "foundation/production"
    assert len(updated_plan["tools"]) == 2  # New profile has 2 tools
    assert updated_plan["tools"][0]["name"] == "bash"
    assert updated_plan["tools"][1]["name"] == "grep"


@pytest.mark.skip(reason="Needs update for bundle system")
@pytest.mark.asyncio
async def test_profile_change_handles_file_write_error(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
) -> None:
    """Test that file write errors are handled gracefully.

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for profile B
    """
    session_id = "test_session_123"

    # Mock services
    mock_mount_plan_service = Mock()
    mock_mount_plan_service.generate_mount_plan = Mock(return_value=new_mount_plan)

    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)

    # Make the mount plan directory read-only to cause write error
    session_dir = mock_state_dir / "sessions" / session_id
    session_dir.chmod(0o444)

    try:
        with (
            patch("amplifierd.routers.sessions.get_state_dir", return_value=mock_state_dir),
            patch("amplifierd.routers.sessions.change_session_profile", new_callable=AsyncMock),
        ):
            # Expect HTTP 500 error due to file write failure
            with pytest.raises(HTTPException) as exc_info:
                await change_session_profile(
                    session_id=session_id,
                    mount_plan_service=mock_mount_plan_service,
                    session_service=mock_session_service,
                    profile_name="foundation/production",
                )

            assert exc_info.value.status_code == 500
            assert "Failed to persist profile change" in exc_info.value.detail
    finally:
        # Restore permissions for cleanup
        session_dir.chmod(0o755)

@pytest.mark.skip(reason="Needs update for bundle system")
@pytest.mark.asyncio
async def test_profile_change_with_no_active_runner(
    mock_state_dir: Path,
    mock_session_metadata: SessionMetadata,
    new_mount_plan: dict,
) -> None:
    """Test that profile change works even when there's no active ExecutionRunner.

    This verifies that the mount plan is still persisted to disk even if the
    ExecutionRunner doesn't exist yet (which is a valid scenario).

    Args:
        mock_state_dir: Temporary state directory
        mock_session_metadata: Mock session metadata
        new_mount_plan: New mount plan for profile B
    """
    session_id = "test_session_123"
    mount_plan_path = mock_state_dir / "sessions" / session_id / "mount_plan.json"

    # Mock services
    mock_mount_plan_service = Mock()
    mock_mount_plan_service.generate_mount_plan = Mock(return_value=new_mount_plan)

    mock_session_service = Mock()
    mock_session_service.get_session = Mock(return_value=mock_session_metadata)

    def update_session_side_effect(session_id: str, update_fn):  # type: ignore[no-untyped-def]
        update_fn(mock_session_metadata)

    mock_session_service._update_session = Mock(side_effect=update_session_side_effect)

    # Patch change_session_profile to raise ValueError (no active runner)
    with (
        patch("amplifierd.routers.sessions.get_state_dir", return_value=mock_state_dir),
        patch("amplifierd.routers.sessions.change_session_profile", new_callable=AsyncMock) as mock_change,
    ):
        mock_change.side_effect = ValueError("No active ExecutionRunner")

        # Call should succeed even though there's no runner
        result = await change_session_profile(
            session_id=session_id,
            mount_plan_service=mock_mount_plan_service,
            session_service=mock_session_service,
            profile_name="foundation/production",
        )

    # Verify metadata was updated
    assert result.profile_name == "foundation/production"

    # CRITICAL: Verify mount_plan.json was still updated
    with open(mount_plan_path) as f:
        updated_plan = json.load(f)

    assert updated_plan["session"]["settings"]["profile_name"] == "foundation/production"
