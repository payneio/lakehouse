"""Integration tests for spawner module.

Tests complete workflows with real SessionManager and actual file I/O
to verify component interactions and end-to-end functionality.
"""

import json
import sys
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

# Mock amplifierd module before import to avoid dependency issues
sys.modules["amplifierd"] = MagicMock()
sys.modules["amplifierd.module_resolver"] = MagicMock()
sys.modules["amplifier_core"] = MagicMock()

from amplifier_library.models.sessions import SessionStatus
from amplifier_library.sessions.manager import SessionManager
from amplifier_library.sessions.spawner import resume_spawned_agent
from amplifier_library.sessions.spawner import spawn_agent


@pytest.fixture
def storage_dir(tmp_path):
    """Provide temporary storage directory for tests."""
    return tmp_path / "test_storage"


@pytest.fixture
def session_manager(storage_dir):
    """Provide SessionManager instance with temp storage."""
    return SessionManager(storage_dir)


@pytest.fixture
def parent_session():
    """Provide mock parent session with realistic config."""
    session = Mock()
    session.session_id = "parent-session-123"
    session.amplified_dir = "."
    session.config = {
        "session": {
            "orchestrator": "default",
            "timeout": 30,
            "llm": {
                "model": "claude-3-5-sonnet-20241022",
                "temperature": 0.7,
            },
            "tools": ["read", "write"],
        }
    }
    return session


@pytest.fixture
def agent_configs():
    """Provide agent configurations for testing."""
    return {
        "bug-hunter": {
            "session": {
                "tools": ["debug", "test"],
                "context": "focused",
            }
        },
        "test-coverage": {
            "session": {
                "tools": ["pytest", "coverage"],
                "llm": {
                    "temperature": 0.3,  # Override parent
                },
            }
        },
    }


class TestSpawnAgentIntegration:
    """Integration tests for spawn_agent with real SessionManager."""

    @pytest.mark.asyncio
    async def test_end_to_end_spawn_creates_persistent_session(
        self, session_manager, parent_session, agent_configs
    ):
        """Given parent session and agent configs
        When spawning agent end-to-end
        Then should create persisted session with all artifacts
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            # Mock successful execution
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="Found 5 bugs in auth.py")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            # Execute spawn
            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Analyze auth.py for bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify result
            assert result["status"] == "completed"
            assert result["output"] == "Found 5 bugs in auth.py"
            child_id = result["session_id"]

            # Verify session persisted
            metadata = session_manager.get_session(child_id)
            assert metadata is not None
            assert metadata.status == SessionStatus.COMPLETED
            assert metadata.profile_name == "bug-hunter"
            assert metadata.parent_session_id == "parent-session-123"

            # Verify mount_plan.json exists
            session_dir = session_manager.storage_dir / child_id
            mount_plan_path = session_dir / "mount_plan.json"
            assert mount_plan_path.exists()

            mount_plan = json.loads(mount_plan_path.read_text())
            assert mount_plan["session"]["orchestrator"] == "default"  # Inherited
            assert mount_plan["session"]["tools"] == ["debug", "test"]  # From agent

            # Verify transcript saved
            transcript = session_manager.get_transcript(child_id)
            assert len(transcript) == 2
            assert transcript[0].role == "user"
            assert transcript[0].content == "Analyze auth.py for bugs"
            assert transcript[1].role == "assistant"
            assert transcript[1].content == "Found 5 bugs in auth.py"

    @pytest.mark.asyncio
    async def test_spawn_with_config_overlay_affects_behavior(
        self, session_manager, parent_session, agent_configs
    ):
        """Given agent with temperature override in config
        When spawning agent
        Then merged config should reflect agent-specific settings
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(return_value="Coverage: 85%")
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session_class.return_value = mock_session

            result = await spawn_agent(
                parent_session=parent_session,
                agent_name="test-coverage",
                instruction="Analyze test coverage",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify AmplifierSession created with merged config
            call_args = mock_session_class.call_args
            merged_config = call_args[0][0]

            # Verify override
            assert merged_config["session"]["llm"]["temperature"] == 0.3  # Agent override
            assert merged_config["session"]["llm"]["model"] == "claude-3-5-sonnet-20241022"  # Inherited

            # Verify agent-specific tools
            assert merged_config["session"]["tools"] == ["pytest", "coverage"]

    @pytest.mark.asyncio
    async def test_spawn_failure_persists_error_state(self, session_manager, parent_session, agent_configs):
        """Given agent execution that fails
        When spawning agent
        Then should persist FAILED status with error details
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=RuntimeError("LLM API timeout"))
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
            child_id = result["session_id"]

            # Verify failed status persisted
            metadata = session_manager.get_session(child_id)
            assert metadata.status == SessionStatus.FAILED
            assert metadata.error_message is not None
            assert "LLM API timeout" in metadata.error_message


class TestResumeAgentIntegration:
    """Integration tests for resume_spawned_agent with real SessionManager."""

    @pytest.mark.asyncio
    async def test_end_to_end_spawn_and_resume(self, session_manager, parent_session, agent_configs):
        """Given spawned agent session
        When resuming with new instruction
        Then should continue with preserved config and history
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            # Setup mocks
            mock_session = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)  # No context module
            mock_session_class.return_value = mock_session

            # First spawn
            mock_session.execute = AsyncMock(return_value="Found bugs in auth.py")
            spawn_result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Analyze auth.py",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = spawn_result["session_id"]

            # Resume with new instruction
            mock_session.execute = AsyncMock(return_value="Fixed 3 bugs")
            resume_result = await resume_spawned_agent(
                session_id=child_id,
                instruction="Fix the bugs you found",
                session_manager=session_manager,
            )

            assert resume_result["status"] == "completed"
            assert resume_result["output"] == "Fixed 3 bugs"
            assert resume_result["session_id"] == child_id

            # Verify transcript has all messages
            transcript = session_manager.get_transcript(child_id)
            assert len(transcript) == 4  # 2 from spawn + 2 from resume
            assert transcript[0].content == "Analyze auth.py"
            assert transcript[1].content == "Found bugs in auth.py"
            assert transcript[2].content == "Fix the bugs you found"
            assert transcript[3].content == "Fixed 3 bugs"

    @pytest.mark.asyncio
    async def test_resume_loads_transcript_into_context(self, session_manager, parent_session, agent_configs):
        """Given spawned session with transcript
        When resuming
        Then should load historical messages into context module
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            # First spawn to create history
            mock_session = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            mock_session.execute = AsyncMock(return_value="Initial response")
            spawn_result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="First task",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = spawn_result["session_id"]

            # Resume with context module available
            mock_context = AsyncMock()
            mock_context.add_message = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=mock_context)
            mock_session.execute = AsyncMock(return_value="Continued response")

            await resume_spawned_agent(
                session_id=child_id,
                instruction="Continue task",
                session_manager=session_manager,
            )

            # Verify historical messages loaded
            assert mock_context.add_message.call_count == 2  # user + assistant from spawn
            calls = mock_context.add_message.call_args_list
            assert calls[0][0][0]["content"] == "First task"
            assert calls[1][0][0]["content"] == "Initial response"

    @pytest.mark.asyncio
    async def test_resume_failed_session_resets_to_active(self, session_manager, parent_session, agent_configs):
        """Given failed session
        When resuming
        Then should reset to active and allow retry
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            # Spawn with failure
            mock_session.execute = AsyncMock(side_effect=RuntimeError("API error"))
            spawn_result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="First attempt",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = spawn_result["session_id"]

            # Verify failed
            metadata = session_manager.get_session(child_id)
            assert metadata.status == SessionStatus.FAILED

            # Resume successfully
            mock_session.execute = AsyncMock(return_value="Success on retry")
            resume_result = await resume_spawned_agent(
                session_id=child_id,
                instruction="Retry task",
                session_manager=session_manager,
            )

            assert resume_result["status"] == "completed"

            # Verify status reset and completed
            metadata = session_manager.get_session(child_id)
            assert metadata.status == SessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_multiple_resume_cycles(self, session_manager, parent_session, agent_configs):
        """Given spawned session
        When resuming multiple times
        Then should handle multi-turn conversations
        """
        with (
            patch("amplifier_core.AmplifierSession") as mock_session_class,
            patch("amplifierd.module_resolver.DaemonModuleSourceResolver"),
            patch("amplifier_library.storage.paths.get_share_dir"),
        ):
            mock_session = AsyncMock()
            mock_session.cleanup = AsyncMock()
            mock_session.coordinator = Mock()
            mock_session.coordinator.mount = AsyncMock()
            mock_session.coordinator.get = Mock(return_value=None)
            mock_session_class.return_value = mock_session

            # Initial spawn
            mock_session.execute = AsyncMock(return_value="Turn 1")
            spawn_result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Task 1",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = spawn_result["session_id"]

            # Resume turn 2
            mock_session.execute = AsyncMock(return_value="Turn 2")
            await resume_spawned_agent(child_id, "Task 2", session_manager)

            # Resume turn 3
            mock_session.execute = AsyncMock(return_value="Turn 3")
            await resume_spawned_agent(child_id, "Task 3", session_manager)

            # Verify complete transcript
            transcript = session_manager.get_transcript(child_id)
            assert len(transcript) == 6  # 3 turns × 2 messages each

            assert transcript[0].content == "Task 1"
            assert transcript[1].content == "Turn 1"
            assert transcript[2].content == "Task 2"
            assert transcript[3].content == "Turn 2"
            assert transcript[4].content == "Task 3"
            assert transcript[5].content == "Turn 3"


class TestSessionHierarchy:
    """Test parent-child session relationships."""

    @pytest.mark.asyncio
    async def test_child_session_references_parent(self, session_manager, parent_session, agent_configs):
        """Given spawned child session
        When querying metadata
        Then should reference parent session ID
        """
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

            child_id = result["session_id"]
            metadata = session_manager.get_session(child_id)

            assert metadata.parent_session_id == "parent-session-123"
            assert child_id.startswith("parent-session-123-")

    @pytest.mark.asyncio
    async def test_multiple_children_from_same_parent(self, session_manager, parent_session, agent_configs):
        """Given parent session
        When spawning multiple different agents
        Then should create separate child sessions with unique IDs
        """
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

            # Spawn first agent
            result1 = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="Find bugs",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Spawn second agent
            result2 = await spawn_agent(
                parent_session=parent_session,
                agent_name="test-coverage",
                instruction="Check coverage",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            # Verify unique sessions
            child_id1 = result1["session_id"]
            child_id2 = result2["session_id"]

            assert child_id1 != child_id2
            assert child_id1.endswith("_bug-hunter")
            assert child_id2.endswith("_test-coverage")

            # Both reference same parent
            meta1 = session_manager.get_session(child_id1)
            meta2 = session_manager.get_session(child_id2)

            assert meta1.parent_session_id == meta2.parent_session_id
            assert meta1.parent_session_id == "parent-session-123"


class TestConfigPersistence:
    """Test configuration persistence across spawn and resume."""

    @pytest.mark.asyncio
    async def test_mount_plan_persisted_correctly(self, session_manager, parent_session, agent_configs):
        """Given agent spawn with merged config
        When session completes
        Then mount_plan.json should contain complete merged config
        """
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
                agent_name="test-coverage",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = result["session_id"]
            session_dir = session_manager.storage_dir / child_id
            mount_plan_path = session_dir / "mount_plan.json"

            assert mount_plan_path.exists()

            mount_plan = json.loads(mount_plan_path.read_text())

            # Verify merged config
            assert mount_plan["session"]["orchestrator"] == "default"  # From parent
            assert mount_plan["session"]["timeout"] == 30  # From parent
            assert mount_plan["session"]["tools"] == ["pytest", "coverage"]  # From agent
            assert mount_plan["session"]["llm"]["model"] == "claude-3-5-sonnet-20241022"  # From parent
            assert mount_plan["session"]["llm"]["temperature"] == 0.3  # Agent override

    @pytest.mark.asyncio
    async def test_resume_uses_exact_persisted_config(self, session_manager, parent_session, agent_configs):
        """Given persisted mount_plan
        When resuming session
        Then should load exact config from disk
        """
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

            # Spawn
            spawn_result = await spawn_agent(
                parent_session=parent_session,
                agent_name="bug-hunter",
                instruction="test",
                agent_configs=agent_configs,
                session_manager=session_manager,
            )

            child_id = spawn_result["session_id"]

            # Get persisted config
            session_dir = session_manager.storage_dir / child_id
            mount_plan_path = session_dir / "mount_plan.json"
            persisted_config = json.loads(mount_plan_path.read_text())

            # Resume
            await resume_spawned_agent(child_id, "continue", session_manager)

            # Verify AmplifierSession created with persisted config
            call_args = mock_session_class.call_args_list[-1]  # Last call (resume)
            loaded_config = call_args[0][0]

            assert loaded_config == persisted_config
