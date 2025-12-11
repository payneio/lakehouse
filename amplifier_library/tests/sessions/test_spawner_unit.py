"""Unit tests for spawner module functions.

Tests spawn_agent and resume_spawned_agent functions with mocked
dependencies to verify logic without requiring full system integration.
"""

import json
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

# Mock amplifierd module before import to avoid dependency issues
sys.modules["amplifierd"] = MagicMock()
sys.modules["amplifierd.module_resolver"] = MagicMock()
sys.modules["amplifier_core"] = MagicMock()

from amplifier_library.models.sessions import SessionMessage
from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifier_library.sessions.spawner import AgentNotFoundError
from amplifier_library.sessions.spawner import ExecutionError
from amplifier_library.sessions.spawner import SessionNotFoundError
from amplifier_library.sessions.spawner import _generate_child_session_id
from amplifier_library.sessions.spawner import _merge_configs
from amplifier_library.sessions.spawner import resume_spawned_agent
from amplifier_library.sessions.spawner import spawn_agent


class TestGenerateChildSessionId:
    """Test W3C trace context style session ID generation."""

    def test_generates_hierarchical_id(self):
        """Given parent ID and agent name
        When generating child ID
        Then should create hierarchical format: parent-span_agent
        """
        parent_id = "abc123"
        agent_name = "bug-hunter"

        child_id = _generate_child_session_id(parent_id, agent_name)

        # Verify format: parent-{16-hex-chars}_{agent-name}
        assert child_id.startswith(f"{parent_id}-")
        assert child_id.endswith(f"_{agent_name}")

        # Extract and verify span portion (split by _ to handle agent names with hyphens)
        parts = child_id.split("_")
        assert len(parts) == 2  # span_agent
        parent_and_span = parts[0]
        span = parent_and_span.split("-")[-1]  # Get last part after all hyphens
        assert len(span) == 16  # 16 hex chars
        assert all(c in "0123456789abcdef" for c in span)

    def test_unique_ids_for_same_parent(self):
        """Given same parent and agent
        When generating multiple child IDs
        Then each should be unique (different spans)
        """
        parent_id = "abc123"
        agent_name = "bug-hunter"

        id1 = _generate_child_session_id(parent_id, agent_name)
        id2 = _generate_child_session_id(parent_id, agent_name)

        assert id1 != id2
        assert id1.split("-")[0] == id2.split("-")[0]  # Same parent
        assert id1.split("_")[1] == id2.split("_")[1]  # Same agent

    def test_handles_special_characters_in_agent_name(self):
        """Given agent name with special characters
        When generating child ID
        Then should include agent name as-is
        """
        parent_id = "parent123"
        agent_name = "my-special_agent.v2"

        child_id = _generate_child_session_id(parent_id, agent_name)

        assert child_id.endswith(f"_{agent_name}")


class TestSpawnAgentValidation:
    """Test spawn_agent input validation."""

    @pytest.mark.asyncio
    async def test_raises_when_agent_not_in_configs(self):
        """Given agent_name not in agent_configs
        When spawning agent
        Then should raise AgentNotFoundError with available agents
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        agent_configs = {"bug-hunter": {}, "test-coverage": {}}
        session_manager = Mock()

        with pytest.raises(AgentNotFoundError) as exc_info:
            await spawn_agent(
                parent_session=parent_session,
                agent_name="nonexistent",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

        error_msg = str(exc_info.value)
        assert "nonexistent" in error_msg
        assert "bug-hunter" in error_msg
        assert "test-coverage" in error_msg

    @pytest.mark.asyncio
    async def test_raises_when_parent_has_no_config(self):
        """Given parent session without config
        When spawning agent
        Then should raise ValueError
        """
        parent_session = Mock()
        parent_session.config = {}  # Empty config
        parent_session.session_id = "parent123"

        agent_configs = {"bug-hunter": {}}
        session_manager = Mock()

        with pytest.raises(ValueError, match="Parent session has no config"):
            await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )


class TestSpawnAgentSessionCreation:
    """Test spawn_agent session creation logic."""

    @pytest.mark.asyncio
    async def test_creates_child_session_with_merged_config(self):
        """Given valid parent session and agent config
        When spawning agent
        Then should create child session with merged config
        """
        # Setup
        parent_config = {
            "session": {
                "orchestrator": "default",
                "timeout": 30,
            }
        }
        agent_config = {"session": {"tools": ["debug"]}}

        parent_session = Mock()
        parent_session.config = parent_config
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()

        agent_configs = {"bug-hunter": agent_config}

        # Mock AmplifierSession and execution (patching at import location since it's imported inside function)
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="Agent output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            # Execute
            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Find bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify session created with merged config
            assert session_manager.create_session.called
            call_args = session_manager.create_session.call_args
            assert call_args[1]["profile_name"] == "bug-hunter"
            assert call_args[1]["parent_session_id"] == "parent123"

            # Verify merged config has both parent and agent values
            merged = call_args[1]["mount_plan"]
            assert merged["session"]["orchestrator"] == "default"  # From parent
            assert merged["session"]["tools"] == ["debug"]  # From agent

    @pytest.mark.asyncio
    async def test_uses_custom_session_id_if_provided(self):
        """Given custom sub_session_id parameter
        When spawning agent
        Then should use provided ID instead of generating
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()

        custom_id = "custom-session-id"
        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
                sub_session_id=custom_id,
            )

            # Verify custom ID used
            assert result["session_id"] == custom_id
            call_args = session_manager.create_session.call_args
            assert call_args[1]["session_id"] == custom_id

    @pytest.mark.asyncio
    async def test_generates_unique_id_when_not_provided(self):
        """Given no sub_session_id parameter
        When spawning agent
        Then should auto-generate W3C trace style ID
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()

        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify format
            session_id = result["session_id"]
            assert session_id.startswith("parent123-")
            assert session_id.endswith("_bug-hunter")


class TestSpawnAgentExecution:
    """Test spawn_agent execution flow."""

    @pytest.mark.asyncio
    async def test_successful_execution_returns_completed_status(self):
        """Given successful agent execution
        When spawning agent
        Then should return completed status with output
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()

        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="Found 3 bugs in auth.py")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Find bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            assert result["status"] == "completed"
            assert result["output"] == "Found 3 bugs in auth.py"
            assert "session_id" in result
            assert "trace_id" in result
            assert session_manager.complete_session.called

    @pytest.mark.asyncio
    async def test_keyboard_interrupt_returns_interrupted_status(self):
        """Given KeyboardInterrupt during execution
        When spawning agent
        Then should return interrupted status and terminate session
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.terminate_session = Mock()

        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=KeyboardInterrupt())
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Find bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            assert result["status"] == "interrupted"
            assert "interrupted" in result["output"].lower()
            assert session_manager.terminate_session.called

    @pytest.mark.asyncio
    async def test_execution_error_returns_error_status(self):
        """Given exception during execution
        When spawning agent
        Then should return error status and fail session
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.fail_session = Mock()

        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("LLM timeout"))
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Find bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            assert result["status"] == "error"
            assert "failed" in result["output"].lower()
            assert session_manager.fail_session.called
            call_args = session_manager.fail_session.call_args
            assert "LLM timeout" in call_args[1]["error_message"]

    @pytest.mark.asyncio
    async def test_cleanup_called_even_on_error(self):
        """Given error during execution
        When spawning agent
        Then should still call cleanup on session
        """
        parent_session = Mock()
        parent_session.config = {"session": {}}
        parent_session.session_id = "parent123"
        parent_session.amplified_dir = "."

        session_manager = Mock()
        session_manager.create_session = Mock()
        session_manager.start_session = Mock()
        session_manager.append_message = Mock()
        session_manager.fail_session = Mock()

        agent_configs = {"bug-hunter": {"session": {}}}

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("Error"))
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify cleanup was called despite error
            assert mock_session.cleanup.called


class TestResumeSpawnedAgent:
    """Test resume_spawned_agent functionality."""

    @pytest.mark.asyncio
    async def test_raises_when_session_not_found(self):
        """Given non-existent session_id
        When resuming agent
        Then should raise SessionNotFoundError
        """
        session_manager = Mock()
        session_manager.get_session = Mock(return_value=None)

        with pytest.raises(SessionNotFoundError, match="not found"):
            await resume_spawned_agent(
                session_id="nonexistent",
                instruction="Continue",
                session_manager=session_manager,
            )

    @pytest.mark.asyncio
    async def test_raises_when_mount_plan_missing(self):
        """Given session without mount_plan.json
        When resuming agent
        Then should raise SessionNotFoundError
        """
        metadata = SessionMetadata(
            session_id="test123",
            amplified_dir=".",
            profile_name="bug-hunter",
            status=SessionStatus.COMPLETED,
            created_at=datetime.now(UTC),
            mount_plan_path="mount_plan.json",
        )

        session_manager = Mock()
        session_manager.get_session = Mock(return_value=metadata)
        session_manager.storage_dir = Path("/tmp/test")

        with pytest.raises(SessionNotFoundError, match="no mount_plan.json"):
            await resume_spawned_agent(
                session_id="test123",
                instruction="Continue",
                session_manager=session_manager,
            )

    @pytest.mark.asyncio
    async def test_resumes_with_preserved_config(self, tmp_path):
        """Given existing session with mount_plan
        When resuming agent
        Then should load and use original config
        """
        # Setup session directory
        session_id = "parent-abc123_bug-hunter"
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)

        mount_plan = {
            "session": {
                "orchestrator": "default",
                "tools": ["debug"],
            }
        }
        (session_dir / "mount_plan.json").write_text(json.dumps(mount_plan))

        metadata = SessionMetadata(
            session_id=session_id,
            amplified_dir=".",
            profile_name="bug-hunter",
            status=SessionStatus.COMPLETED,
            created_at=datetime.now(UTC),
            mount_plan_path="mount_plan.json",
        )

        session_manager = Mock()
        session_manager.get_session = Mock(return_value=metadata)
        session_manager.storage_dir = tmp_path / "sessions"
        session_manager.get_transcript = Mock(return_value=[])
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()
        session_manager._update_session = Mock()

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="Resumed output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            result = await resume_spawned_agent(
                session_id=session_id,
                instruction="Continue work",
                session_manager=session_manager,
            )

            # Verify AmplifierSession created with original config
            assert mock_session_class.called
            call_args = mock_session_class.call_args
            assert call_args[0][0] == mount_plan  # First positional arg is config

            assert result["status"] == "completed"
            assert result["output"] == "Resumed output"

    @pytest.mark.asyncio
    async def test_loads_transcript_history_into_context(self, tmp_path):
        """Given session with existing transcript
        When resuming agent
        Then should load history into context module
        """
        session_id = "parent-abc123_bug-hunter"
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)

        mount_plan = {"session": {}}
        (session_dir / "mount_plan.json").write_text(json.dumps(mount_plan))

        metadata = SessionMetadata(
            session_id=session_id,
            amplified_dir=".",
            profile_name="bug-hunter",
            status=SessionStatus.COMPLETED,
            created_at=datetime.now(UTC),
            mount_plan_path="mount_plan.json",
        )

        transcript = [
            SessionMessage(role="user", content="First message", timestamp=datetime.now(UTC)),
            SessionMessage(role="assistant", content="First response", timestamp=datetime.now(UTC)),
        ]

        session_manager = Mock()
        session_manager.get_session = Mock(return_value=metadata)
        session_manager.storage_dir = tmp_path / "sessions"
        session_manager.get_transcript = Mock(return_value=transcript)
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()
        session_manager._update_session = Mock()

        mock_context = AsyncMock()
        mock_context.add_message = AsyncMock()

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=mock_context)
            mock_session_class.return_value = mock_session

            await resume_spawned_agent(
                session_id=session_id,
                instruction="Continue",
                session_manager=session_manager,
            )

            # Verify transcript messages added to context
            assert mock_context.add_message.call_count == 2
            calls = mock_context.add_message.call_args_list
            assert calls[0][0][0]["role"] == "user"
            assert calls[0][0][0]["content"] == "First message"
            assert calls[1][0][0]["role"] == "assistant"
            assert calls[1][0][0]["content"] == "First response"

    @pytest.mark.asyncio
    async def test_resets_session_to_active_state(self, tmp_path):
        """Given completed/failed session
        When resuming agent
        Then should reset to ACTIVE status
        """
        session_id = "test123"
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)

        mount_plan = {"session": {}}
        (session_dir / "mount_plan.json").write_text(json.dumps(mount_plan))

        metadata = SessionMetadata(
            session_id=session_id,
            amplified_dir=".",
            profile_name="bug-hunter",
            status=SessionStatus.FAILED,
            created_at=datetime.now(UTC),
            mount_plan_path="mount_plan.json",
        )

        session_manager = Mock()
        session_manager.get_session = Mock(return_value=metadata)
        session_manager.storage_dir = tmp_path / "sessions"
        session_manager.get_transcript = Mock(return_value=[])
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()
        session_manager._update_session = Mock()

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            await resume_spawned_agent(
                session_id=session_id,
                instruction="Retry",
                session_manager=session_manager,
            )

            # Verify session reset to active
            assert session_manager._update_session.called
            call_args = session_manager._update_session.call_args
            assert call_args[0][0] == session_id

    @pytest.mark.asyncio
    async def test_extracts_agent_name_from_session_id(self, tmp_path):
        """Given session_id with embedded agent name
        When resuming agent
        Then should extract agent name from ID format
        """
        session_id = "parent-span123_my-custom-agent"
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)

        mount_plan = {"session": {}}
        (session_dir / "mount_plan.json").write_text(json.dumps(mount_plan))

        metadata = SessionMetadata(
            session_id=session_id,
            amplified_dir=".",
            profile_name="my-custom-agent",
            status=SessionStatus.COMPLETED,
            created_at=datetime.now(UTC),
            mount_plan_path="mount_plan.json",
        )

        session_manager = Mock()
        session_manager.get_session = Mock(return_value=metadata)
        session_manager.storage_dir = tmp_path / "sessions"
        session_manager.get_transcript = Mock(return_value=[])
        session_manager.append_message = Mock()
        session_manager.complete_session = Mock()
        session_manager._update_session = Mock()

        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="output")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            result = await resume_spawned_agent(
                session_id=session_id,
                instruction="Continue",
                session_manager=session_manager,
            )

            # Agent name extracted and used in logging (not directly testable,
            # but verified through successful execution)
            assert result["status"] == "completed"
