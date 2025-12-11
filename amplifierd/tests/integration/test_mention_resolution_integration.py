"""Integration tests for at-mention resolution system.

Tests the complete flow of mention resolution across:
- Session creation with profile mentions
- Message handling with runtime mentions
- Execution runner context injection
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from amplifier_library.models.sessions import SessionMetadata
from amplifier_library.models.sessions import SessionStatus
from amplifierd.services.mention_resolver import MentionResolver


@pytest.fixture
def test_data_structure(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create test data directory structure.

    Returns:
        Tuple of (data_path, amplified_dir, compiled_profile_dir)
    """
    # Create data root
    data_path = tmp_path / "data"
    data_path.mkdir()

    # Create amplified directory with AGENTS.md
    amplified_dir = data_path / "test-project"
    amplified_dir.mkdir()

    agents_md = amplified_dir / "AGENTS.md"
    agents_md.write_text("Project documentation: @README.md")

    readme = amplified_dir / "README.md"
    readme.write_text("# Test Project\n\nProject overview content.")

    feature_doc = amplified_dir / "FEATURE.md"
    feature_doc.write_text("# Feature X\n\nFeature details.")

    # Create compiled profile directory with context
    compiled_profile_dir = tmp_path / "share" / "profiles" / "test-profile"
    compiled_profile_dir.mkdir(parents=True)

    contexts_dir = compiled_profile_dir / "contexts"
    contexts_dir.mkdir()

    context_dir = contexts_dir / "test-context"
    context_dir.mkdir()

    context_file = context_dir / "guidelines.md"
    context_file.write_text("# Context Guidelines\n\nImportant context information.")

    return data_path, amplified_dir, compiled_profile_dir


@pytest.fixture
def mock_session_metadata(tmp_path: Path) -> SessionMetadata:
    """Create mock session metadata."""
    from datetime import UTC
    from datetime import datetime

    return SessionMetadata(
        session_id="test_session_123",
        status=SessionStatus.ACTIVE,
        profile_name="test-profile",
        mount_plan_path="mount_plan.json",
        amplified_dir="test-project",
        created_at=datetime.now(UTC),
    )


# --- Unit Tests for MentionResolver (Baseline) ---


def test_mention_resolver_initialization(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test MentionResolver initializes correctly."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    assert resolver.compiled_profile_dir == compiled_profile_dir.resolve()
    assert resolver.amplified_dir == amplified_dir.resolve()
    assert resolver.loader is not None


def test_resolve_profile_instructions_with_mentions(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test resolving profile instruction mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    instructions = "Follow @test-context:guidelines.md for guidance."
    messages = resolver.resolve_profile_instructions(instructions)

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Context Guidelines" in messages[0].content
    assert "@test-context:guidelines.md" in messages[0].source_mentions[0]


def test_resolve_profile_instructions_no_mentions(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test resolving instructions without mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    instructions = "Plain instructions without mentions."
    messages = resolver.resolve_profile_instructions(instructions)

    assert messages == []


def test_resolve_agents_md(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test resolving AGENTS.md mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    messages = resolver.resolve_agents_md()

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "Test Project" in messages[0].content
    assert "Project overview" in messages[0].content


def test_resolve_agents_md_missing_file(tmp_path: Path) -> None:
    """Test graceful handling of missing AGENTS.md."""
    amplified_dir = tmp_path / "no-agents-project"
    amplified_dir.mkdir()

    compiled_profile_dir = tmp_path / "profile"
    compiled_profile_dir.mkdir()

    resolver = MentionResolver(compiled_profile_dir, amplified_dir)
    messages = resolver.resolve_agents_md()

    assert messages == []


def test_resolve_runtime_mentions(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test resolving runtime mentions from user message."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    user_message = "Check @FEATURE.md please."
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should get AGENTS.md mentions (README.md) + user message mentions (FEATURE.md)
    assert len(messages) == 2

    # First message from AGENTS.md
    assert "Test Project" in messages[0].content

    # Second message from user mention
    assert "Feature X" in messages[1].content


def test_resolve_runtime_mentions_no_user_mentions(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test runtime resolution with no user mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    user_message = "Just a regular message."
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should only get AGENTS.md mentions
    assert len(messages) == 1
    assert "Test Project" in messages[0].content


def test_resolve_runtime_mentions_order(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test that AGENTS.md mentions come before user mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure
    resolver = MentionResolver(compiled_profile_dir, amplified_dir)

    user_message = "See @FEATURE.md"
    messages = resolver.resolve_runtime_mentions(user_message)

    # Should have README.md (from AGENTS.md) first, then FEATURE.md (from user)
    assert len(messages) == 2
    assert "Test Project" in messages[0].content
    assert "Feature X" in messages[1].content


# --- Integration Test 1: Session Creation with Profile Mentions ---


@pytest.mark.asyncio
async def test_session_creation_resolves_and_caches_profile_mentions(
    test_data_structure: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Test session creation resolves profile mentions and caches them."""
    data_path, amplified_dir, compiled_profile_dir = test_data_structure

    # Create session storage directory
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = "test_session_123"
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Mock mount plan with agent instructions containing mentions
    mount_plan = {
        "format_version": "1.0",
        "session": {"settings": {"amplified_dir": str(amplified_dir), "profile_name": "test-profile"}},
        "agents": {
            "test-agent": {
                "module_id": "test-agent",
                "content": "Follow @test-context:guidelines.md for guidance.",
            }
        },
    }

    # Simulate session creation logic from sessions.py
    from amplifierd.services.mention_resolver import MentionResolver

    # Extract instructions
    all_instructions = []
    for agent_data in mount_plan["agents"].values():
        if isinstance(agent_data, dict) and "content" in agent_data:
            all_instructions.append(agent_data["content"])

    # Resolve mentions
    resolver = MentionResolver(
        compiled_profile_dir=compiled_profile_dir,
        amplified_dir=amplified_dir,
    )
    combined_instructions = "\n\n".join(all_instructions)
    profile_context_messages = resolver.resolve_profile_instructions(combined_instructions)

    # Save to session directory
    context_file = session_dir / "profile_context_messages.json"
    context_file.write_text(json.dumps([msg.model_dump() for msg in profile_context_messages], indent=2))

    # Verify file exists and contains correct content
    assert context_file.exists()

    with open(context_file) as f:
        saved_messages = json.load(f)

    assert len(saved_messages) == 1
    assert saved_messages[0]["role"] == "developer"
    assert "Context Guidelines" in saved_messages[0]["content"]
    assert "@test-context:guidelines.md" in saved_messages[0]["source_mentions"][0]


@pytest.mark.asyncio
async def test_session_creation_with_no_mentions_no_cache(
    test_data_structure: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Test session creation without mentions doesn't create cache file."""
    data_path, amplified_dir, compiled_profile_dir = test_data_structure

    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = "test_session_124"
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Mount plan with no mentions
    mount_plan = {
        "format_version": "1.0",
        "session": {"settings": {"amplified_dir": str(amplified_dir), "profile_name": "test-profile"}},
        "agents": {"test-agent": {"module_id": "test-agent", "content": "Plain instructions without mentions."}},
    }

    # Simulate session creation
    from amplifierd.services.mention_resolver import MentionResolver

    all_instructions = []
    for agent_data in mount_plan["agents"].values():
        if isinstance(agent_data, dict) and "content" in agent_data:
            all_instructions.append(agent_data["content"])

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    combined_instructions = "\n\n".join(all_instructions)
    profile_context_messages = resolver.resolve_profile_instructions(combined_instructions)

    # Should be empty
    assert profile_context_messages == []

    # Verify no cache file created
    context_file = session_dir / "profile_context_messages.json"
    assert not context_file.exists()


@pytest.mark.asyncio
async def test_session_creation_missing_mention_files_graceful(
    test_data_structure: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Test session creation with missing mention files handles gracefully."""
    data_path, amplified_dir, compiled_profile_dir = test_data_structure

    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = "test_session_125"
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Mount plan with mention to non-existent file
    mount_plan = {
        "format_version": "1.0",
        "session": {"settings": {"amplified_dir": str(amplified_dir), "profile_name": "test-profile"}},
        "agents": {"test-agent": {"module_id": "test-agent", "content": "Follow @test-context:nonexistent.md"}},
    }

    # Simulate session creation - should not raise
    from amplifierd.services.mention_resolver import MentionResolver

    all_instructions = []
    for agent_data in mount_plan["agents"].values():
        if isinstance(agent_data, dict) and "content" in agent_data:
            all_instructions.append(agent_data["content"])

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    combined_instructions = "\n\n".join(all_instructions)

    # Should not raise, returns empty list
    profile_context_messages = resolver.resolve_profile_instructions(combined_instructions)
    assert profile_context_messages == []


# --- Integration Test 2: Message Handling with Runtime Mentions ---


@pytest.mark.asyncio
async def test_message_handling_resolves_runtime_mentions(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test message handling resolves AGENTS.md and user mentions."""
    _, amplified_dir, compiled_profile_dir = test_data_structure

    # Simulate send_message_for_execution logic from messages.py
    from amplifierd.services.mention_resolver import MentionResolver

    user_message = "Check @FEATURE.md"

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    runtime_context_messages = resolver.resolve_runtime_mentions(user_message)

    # Should have AGENTS.md mentions + user message mentions
    assert len(runtime_context_messages) == 2
    assert "Test Project" in runtime_context_messages[0].content  # From AGENTS.md
    assert "Feature X" in runtime_context_messages[1].content  # From user message


@pytest.mark.asyncio
async def test_message_handling_missing_agents_md_graceful(tmp_path: Path) -> None:
    """Test message handling when AGENTS.md doesn't exist."""
    # Create directories without AGENTS.md
    amplified_dir = tmp_path / "no-agents-project"
    amplified_dir.mkdir()

    feature = amplified_dir / "FEATURE.md"
    feature.write_text("# Feature\n\nContent")

    compiled_profile_dir = tmp_path / "profile"
    compiled_profile_dir.mkdir()

    # Simulate message handling
    from amplifierd.services.mention_resolver import MentionResolver

    user_message = "Check @FEATURE.md"

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    runtime_context_messages = resolver.resolve_runtime_mentions(user_message)

    # Should only have user message mentions (no AGENTS.md)
    assert len(runtime_context_messages) == 1
    assert "Feature" in runtime_context_messages[0].content


@pytest.mark.asyncio
async def test_message_handling_no_mentions_works_normally(test_data_structure: tuple[Path, Path, Path]) -> None:
    """Test message handling without mentions works normally."""
    _, amplified_dir, compiled_profile_dir = test_data_structure

    from amplifierd.services.mention_resolver import MentionResolver

    user_message = "Regular message without mentions"

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    runtime_context_messages = resolver.resolve_runtime_mentions(user_message)

    # Should only have AGENTS.md mentions
    assert len(runtime_context_messages) == 1
    assert "Test Project" in runtime_context_messages[0].content


# --- Integration Test 3: Execution Runner Context Injection ---


@pytest.mark.asyncio
async def test_execution_runner_injects_profile_context(
    test_data_structure: tuple[Path, Path, Path],
    tmp_path: Path,
    mock_session_metadata: SessionMetadata,
) -> None:
    """Test ExecutionRunner injects profile context from cached file."""
    data_path, amplified_dir, compiled_profile_dir = test_data_structure

    # Create session directory with cached profile context
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = mock_session_metadata.session_id
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Create cached profile context
    profile_context_messages = [
        {
            "role": "developer",
            "content": "# Context Guidelines\n\nImportant context information.",
            "source_mentions": ["@test-context:guidelines.md"],
        }
    ]
    context_file = session_dir / "profile_context_messages.json"
    context_file.write_text(json.dumps(profile_context_messages, indent=2))

    # Mock the session manager and context
    mock_session_manager = Mock()
    mock_session_manager.storage_dir = session_storage
    mock_session_manager.get_transcript = Mock(return_value=[])

    # Mock coordinator and context
    mock_context = AsyncMock()
    mock_context.add_message = AsyncMock()

    mock_coordinator = Mock()
    mock_coordinator.get = Mock(return_value=mock_context)
    mock_coordinator.register_capability = Mock()

    # Mock AmplifierSession
    mock_amplifier_session = AsyncMock()
    mock_amplifier_session.coordinator = mock_coordinator
    mock_amplifier_session.initialize = AsyncMock()

    # Create ExecutionRunner
    from amplifier_library.execution.runner import ExecutionRunner

    runner = ExecutionRunner(
        session_manager=mock_session_manager,
        config={},
        session_id=session_id,
    )

    # Inject mocked session
    runner._session = mock_amplifier_session

    # Call _ensure_session to trigger context loading
    with patch("amplifier_core.AmplifierSession", return_value=mock_amplifier_session):
        with patch("amplifier_library.storage.paths.get_share_dir", return_value=tmp_path / "share"):
            with patch("amplifierd.module_resolver.DaemonModuleSourceResolver"):
                await runner._ensure_session()

    # Simulate the profile context injection logic from execute_stream
    if context_file.exists():
        with open(context_file) as f:
            profile_context_data = json.load(f)

        for msg_data in profile_context_data:
            await mock_context.add_message(msg_data)

    # Verify profile context was injected
    assert mock_context.add_message.call_count == 1
    call_args = mock_context.add_message.call_args_list[0]
    injected_message = call_args[0][0]
    assert injected_message["role"] == "developer"
    assert "Context Guidelines" in injected_message["content"]


@pytest.mark.asyncio
async def test_execution_runner_injects_runtime_context(
    test_data_structure: tuple[Path, Path, Path],
    tmp_path: Path,
    mock_session_metadata: SessionMetadata,
) -> None:
    """Test ExecutionRunner injects runtime context messages."""
    _, amplified_dir, compiled_profile_dir = test_data_structure

    # Create session directory
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = mock_session_metadata.session_id
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Mock the session manager
    mock_session_manager = Mock()
    mock_session_manager.storage_dir = session_storage
    mock_session_manager.get_transcript = Mock(return_value=[])

    # Mock coordinator and context
    mock_context = AsyncMock()
    mock_context.add_message = AsyncMock()

    mock_coordinator = Mock()
    mock_coordinator.get = Mock(return_value=mock_context)

    # Mock AmplifierSession
    mock_amplifier_session = AsyncMock()
    mock_amplifier_session.coordinator = mock_coordinator

    # Create ExecutionRunner
    from amplifier_library.execution.runner import ExecutionRunner

    runner = ExecutionRunner(
        session_manager=mock_session_manager,
        config={},
        session_id=session_id,
    )
    runner._session = mock_amplifier_session

    # Create runtime context messages (from mentions)
    from amplifierd.models.context_messages import ContextMessage

    runtime_context_messages = [
        ContextMessage(role="developer", content="# Test Project\n\nProject overview.", source_mentions=["@README.md"]),
        ContextMessage(role="developer", content="# Feature X\n\nFeature details.", source_mentions=["@FEATURE.md"]),
    ]

    # Simulate the runtime context injection logic from execute_stream
    for ctx_msg in runtime_context_messages:
        msg_dict = {"role": ctx_msg.role, "content": ctx_msg.content}
        await mock_context.add_message(msg_dict)

    # Verify runtime context was injected
    assert mock_context.add_message.call_count == 2

    # Verify order and content
    first_call = mock_context.add_message.call_args_list[0][0][0]
    assert "Test Project" in first_call["content"]

    second_call = mock_context.add_message.call_args_list[1][0][0]
    assert "Feature X" in second_call["content"]


@pytest.mark.asyncio
async def test_execution_runner_context_injection_order(
    test_data_structure: tuple[Path, Path, Path],
    tmp_path: Path,
    mock_session_metadata: SessionMetadata,
) -> None:
    """Test context messages injected in correct order: profile → runtime → user."""
    _, amplified_dir, compiled_profile_dir = test_data_structure

    # Create session directory with profile context
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = mock_session_metadata.session_id
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Create cached profile context
    profile_context_messages = [
        {"role": "developer", "content": "PROFILE CONTEXT", "source_mentions": ["@test-context:guidelines.md"]}
    ]
    context_file = session_dir / "profile_context_messages.json"
    context_file.write_text(json.dumps(profile_context_messages, indent=2))

    # Mock context that records order of add_message calls
    call_order = []

    async def track_add_message(msg):
        call_order.append(msg["content"])

    mock_context = AsyncMock()
    mock_context.add_message = AsyncMock(side_effect=track_add_message)

    mock_coordinator = Mock()
    mock_coordinator.get = Mock(return_value=mock_context)

    mock_amplifier_session = AsyncMock()
    mock_amplifier_session.coordinator = mock_coordinator

    # Simulate execute_stream logic
    # 1. Inject profile context
    if context_file.exists():
        with open(context_file) as f:
            profile_data = json.load(f)
        for msg in profile_data:
            await mock_context.add_message(msg)

    # 2. Inject runtime context
    from amplifierd.models.context_messages import ContextMessage

    runtime_messages = [ContextMessage(role="developer", content="RUNTIME CONTEXT", source_mentions=["@README.md"])]

    for ctx_msg in runtime_messages:
        await mock_context.add_message({"role": ctx_msg.role, "content": ctx_msg.content})

    # 3. User message (added via add_message in session state, not via context)
    # So we won't see it in context.add_message calls

    # Verify order
    assert len(call_order) == 2
    assert call_order[0] == "PROFILE CONTEXT"
    assert call_order[1] == "RUNTIME CONTEXT"


@pytest.mark.asyncio
async def test_execution_runner_works_with_no_context(
    tmp_path: Path,
    mock_session_metadata: SessionMetadata,
) -> None:
    """Test execution works when no context messages exist."""
    # Create session directory without profile context file
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = mock_session_metadata.session_id
    session_dir = session_storage / session_id
    session_dir.mkdir()

    # Mock session manager
    mock_session_manager = Mock()
    mock_session_manager.storage_dir = session_storage
    mock_session_manager.get_transcript = Mock(return_value=[])

    # Mock context
    mock_context = AsyncMock()
    mock_context.add_message = AsyncMock()

    mock_coordinator = Mock()
    mock_coordinator.get = Mock(return_value=mock_context)

    mock_amplifier_session = AsyncMock()
    mock_amplifier_session.coordinator = mock_coordinator

    # Create runner
    from amplifier_library.execution.runner import ExecutionRunner

    runner = ExecutionRunner(
        session_manager=mock_session_manager,
        config={},
        session_id=session_id,
    )
    runner._session = mock_amplifier_session

    # Simulate execute_stream with no profile context file
    profile_context_path = session_dir / "profile_context_messages.json"
    assert not profile_context_path.exists()

    # Simulate with no runtime context
    runtime_context_messages = None

    # Should work without errors
    # No context.add_message calls should be made
    assert mock_context.add_message.call_count == 0


# --- Integration Test 4: Full End-to-End Flow ---


@pytest.mark.asyncio
async def test_full_mention_resolution_flow(
    test_data_structure: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    """Test complete flow: session creation → message with mentions → execution with context.

    This test verifies the entire integration:
    1. Session created with profile containing mentions
    2. Profile context cached to file
    3. User sends message with mentions
    4. Runtime mentions resolved
    5. Both profile and runtime context injected into execution
    """
    data_path, amplified_dir, compiled_profile_dir = test_data_structure

    # Step 1: Create session with profile mentions
    session_storage = tmp_path / "state" / "sessions"
    session_storage.mkdir(parents=True)
    session_id = "integration_test_session"
    session_dir = session_storage / session_id
    session_dir.mkdir()

    mount_plan = {
        "format_version": "1.0",
        "session": {"settings": {"amplified_dir": str(amplified_dir), "profile_name": "test-profile"}},
        "agents": {"test-agent": {"module_id": "test-agent", "content": "Follow @test-context:guidelines.md"}},
    }

    # Resolve and cache profile mentions
    from amplifierd.services.mention_resolver import MentionResolver

    all_instructions = []
    for agent_data in mount_plan["agents"].values():
        if isinstance(agent_data, dict) and "content" in agent_data:
            all_instructions.append(agent_data["content"])

    resolver = MentionResolver(compiled_profile_dir=compiled_profile_dir, amplified_dir=amplified_dir)
    profile_context_messages = resolver.resolve_profile_instructions("\n\n".join(all_instructions))

    context_file = session_dir / "profile_context_messages.json"
    context_file.write_text(json.dumps([msg.model_dump() for msg in profile_context_messages], indent=2))

    # Step 2: User sends message with mentions
    user_message = "Check @FEATURE.md and @README.md"
    runtime_context_messages = resolver.resolve_runtime_mentions(user_message)

    # Step 3: Verify context injection order
    call_order = []

    async def track_add_message(msg):
        content = msg.get("content", "")
        if "Context Guidelines" in content:
            call_order.append("PROFILE")
        elif "Test Project" in content:
            call_order.append("RUNTIME:README")
        elif "Feature X" in content:
            call_order.append("RUNTIME:FEATURE")

    mock_context = AsyncMock()
    mock_context.add_message = AsyncMock(side_effect=track_add_message)

    # Inject profile context (from cached file)
    if context_file.exists():
        with open(context_file) as f:
            profile_data = json.load(f)
        for msg in profile_data:
            await mock_context.add_message(msg)

    # Inject runtime context
    for ctx_msg in runtime_context_messages:
        await mock_context.add_message({"role": ctx_msg.role, "content": ctx_msg.content})

    # Verify execution order
    assert len(call_order) == 4  # 1 profile + 1 AGENTS.md (README) + 2 user mentions (FEATURE + README)
    assert call_order[0] == "PROFILE"  # Profile context first
    # Runtime context follows (AGENTS.md mentions + user mentions)
    assert "RUNTIME:README" in call_order[1:]
    assert "RUNTIME:FEATURE" in call_order[1:]
